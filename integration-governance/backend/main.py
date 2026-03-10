from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.collector import calculate_score, classify
from backend.cpi_connector import CPIConnector, convert_cpi_to_integration
from backend.database import Base, SessionLocal, engine, sync_schema
from backend.models import Integration, User, UserSession
from backend.schemas import (
    AlertItem,
    AlertResponse,
    CPISettingsRequest,
    CPISettingsResponse,
    IntegrationRead,
    LoginRequest,
    PaginatedIntegrationsResponse,
    RegisterRequest,
    SummaryResponse,
    SyncCPIRequest,
    UserRead,
)
from backend.security import (
    LOCKOUT_MINUTES,
    MAX_FAILED_LOGINS,
    SESSION_COOKIE_NAME,
    create_session_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    hash_session_token,
    session_expiration,
    validate_password_strength,
    verify_password,
)


BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="GDEP")
Base.metadata.create_all(bind=engine)
sync_schema()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_session_cookie(response: Response, raw_token: str):
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 12,
    )


def clear_session_cookie(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME)


def get_current_user(
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
):
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token_hash = hash_session_token(session_token)
    session = (
        db.query(UserSession)
        .filter(UserSession.token_hash == token_hash)
        .first()
    )
    if session is None or session.expires_at < datetime.utcnow():
        if session is not None:
            db.delete(session)
            db.commit()
        raise HTTPException(status_code=401, detail="Session expired")

    user = db.query(User).filter(User.id == session.user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def compute_score_and_criticality(monthly_volume: int, error_rate: float, business_weight: int):
    score = round(calculate_score(monthly_volume, error_rate, business_weight), 2)
    return score, classify(score)


def build_summary(query):
    total_integrations = query.with_entities(func.count(Integration.id)).scalar() or 0
    average_score = query.with_entities(func.avg(Integration.score)).scalar() or 0
    total_monthly_volume = query.with_entities(func.sum(Integration.monthly_volume)).scalar() or 0
    total_error_count = query.with_entities(func.sum(Integration.error_count)).scalar() or 0

    distribution_rows = (
        query.with_entities(Integration.criticality, func.count(Integration.id))
        .group_by(Integration.criticality)
        .all()
    )
    distribution = {criticality: count for criticality, count in distribution_rows}
    for label in ("Crítica", "Alta", "Média", "Baixa"):
        distribution.setdefault(label, 0)

    return SummaryResponse(
        total_integrations=int(total_integrations),
        average_score=round(float(average_score), 2),
        total_monthly_volume=int(total_monthly_volume),
        total_error_count=int(total_error_count),
        criticality_distribution=distribution,
    )


def deduplicate_cpi_integrations(db: Session, user_id: int):
    duplicate_external_ids = (
        db.query(Integration.external_id)
        .filter(
            Integration.user_id == user_id,
            Integration.external_source == "CPI",
            Integration.external_id.isnot(None),
        )
        .group_by(Integration.external_id)
        .having(func.count(Integration.id) > 1)
        .all()
    )
    for (external_id,) in duplicate_external_ids:
        duplicates = (
            db.query(Integration)
            .filter(
                Integration.user_id == user_id,
                Integration.external_source == "CPI",
                Integration.external_id == external_id,
            )
            .order_by(Integration.id.desc())
            .all()
        )
        for duplicate in duplicates[1:]:
            db.delete(duplicate)


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


@app.post("/auth/register", response_model=UserRead)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    existing = db.query(User).filter(func.lower(User.email) == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado.")

    password_error = validate_password_strength(payload.password)
    if password_error:
        raise HTTPException(status_code=400, detail=password_error)

    password_hash, salt = hash_password(payload.password)
    user = User(
        name=payload.name.strip(),
        email=payload.email.lower(),
        password_hash=password_hash,
        password_salt=salt,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_session_token()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=session_expiration(),
        )
    )
    db.commit()
    set_session_cookie(response, token)
    return user


@app.post("/auth/login", response_model=UserRead)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(func.lower(User.email) == payload.email.lower()).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=423,
            detail=f"Conta bloqueada temporariamente. Tente novamente em {LOCKOUT_MINUTES} minutos.",
        )

    if not verify_password(payload.password, user.password_hash, user.password_salt):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_LOGINS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_login_attempts = 0
        db.commit()
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    user.failed_login_attempts = 0
    user.locked_until = None

    db.query(UserSession).filter(UserSession.user_id == user.id).delete()
    token = create_session_token()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=session_expiration(),
        )
    )
    db.commit()
    set_session_cookie(response, token)
    return user


@app.post("/auth/logout")
def logout(
    response: Response,
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
):
    if session_token:
        db.query(UserSession).filter(
            UserSession.token_hash == hash_session_token(session_token)
        ).delete()
        db.commit()
    clear_session_cookie(response)
    return {"message": "Logout realizado."}


@app.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.get("/me/cpi-settings", response_model=CPISettingsResponse)
def get_cpi_settings(current_user: User = Depends(get_current_user)):
    return CPISettingsResponse(
        cpi_host=current_user.cpi_host,
        cpi_username=current_user.cpi_username,
        cpi_tenant_id=current_user.cpi_tenant_id,
        has_password=bool(current_user.cpi_password_encrypted),
        updated_at=current_user.settings_updated_at,
    )


@app.put("/me/cpi-settings", response_model=CPISettingsResponse)
def update_cpi_settings(
    payload: CPISettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.cpi_host = payload.cpi_host.strip()
    current_user.cpi_username = payload.cpi_username.strip()
    current_user.cpi_password_encrypted = encrypt_secret(payload.cpi_password)
    current_user.cpi_tenant_id = payload.cpi_tenant_id.strip()
    current_user.settings_updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)

    return CPISettingsResponse(
        cpi_host=current_user.cpi_host,
        cpi_username=current_user.cpi_username,
        cpi_tenant_id=current_user.cpi_tenant_id,
        has_password=True,
        updated_at=current_user.settings_updated_at,
    )


@app.get("/integrations", response_model=PaginatedIntegrationsResponse)
def get_integrations(
    criticality: Optional[str] = None,
    platform: Optional[str] = None,
    external_source: Optional[str] = None,
    search: Optional[str] = None,
    min_score: Optional[float] = Query(default=None, ge=0, le=100),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Integration).filter(Integration.user_id == current_user.id)

    if criticality:
        query = query.filter(Integration.criticality == criticality)
    if platform:
        query = query.filter(Integration.platform == platform)
    if external_source:
        query = query.filter(Integration.external_source == external_source)
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            Integration.name.ilike(search_term)
            | Integration.source_system.ilike(search_term)
            | Integration.target_system.ilike(search_term)
        )
    if min_score is not None:
        query = query.filter(Integration.score >= min_score)
    if start_date:
        query = query.filter(Integration.last_synced >= datetime.combine(start_date, time.min))
    if end_date:
        query = query.filter(Integration.last_synced <= datetime.combine(end_date, time.max))

    total = query.with_entities(func.count(Integration.id)).scalar() or 0
    items = (
        query.order_by(Integration.score.desc(), Integration.name.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return PaginatedIntegrationsResponse(items=items, total=int(total), skip=skip, limit=limit)


@app.get("/summary", response_model=SummaryResponse)
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Integration).filter(Integration.user_id == current_user.id)
    return build_summary(query)


@app.get("/alerts", response_model=AlertResponse)
def get_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    integrations = (
        db.query(Integration)
        .filter(Integration.user_id == current_user.id)
        .order_by(Integration.score.desc())
        .all()
    )

    alerts = []
    for integration in integrations:
        if integration.criticality == "Crítica":
            alerts.append(
                AlertItem(
                    integration_id=integration.id,
                    integration_name=integration.name,
                    severity="Alta",
                    message="Integração crítica exige acompanhamento imediato.",
                )
            )
        elif integration.error_rate >= 0.05:
            alerts.append(
                AlertItem(
                    integration_id=integration.id,
                    integration_name=integration.name,
                    severity="Média",
                    message="Taxa de erro acima de 5%.",
                )
            )
        elif integration.avg_processing_time >= 1000:
            alerts.append(
                AlertItem(
                    integration_id=integration.id,
                    integration_name=integration.name,
                    severity="Média",
                    message="Tempo médio de processamento acima de 1000 ms.",
                )
            )

    return AlertResponse(generated_at=datetime.utcnow(), alerts=alerts[:10])


@app.post("/integrations/sync-cpi")
def sync_cpi_integrations(
    payload: SyncCPIRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    decrypted_password = decrypt_secret(current_user.cpi_password_encrypted)
    if not all([current_user.cpi_host, current_user.cpi_username, decrypted_password, current_user.cpi_tenant_id]):
        raise HTTPException(
            status_code=400,
            detail="Configure as credenciais do CPI na página de configurações antes de sincronizar.",
        )

    connector = CPIConnector(
        host=current_user.cpi_host,
        username=current_user.cpi_username,
        password=decrypted_password,
        tenant_id=current_user.cpi_tenant_id,
    )

    if not connector.health_check():
        raise HTTPException(status_code=401, detail="Falha na autenticação CPI. Verifique as credenciais salvas.")

    artifacts = connector.get_integration_artifacts()
    metrics_by_artifact = connector.get_metrics_by_artifact(
        limit=max(payload.message_limit * 100, 2000)
    ) if payload.include_mpl else {}
    total_synced = 0
    seen_external_ids = set()

    for index, artifact in enumerate(artifacts, start=1):
        seen_external_ids.add(artifact["id"])
        existing = (
            db.query(Integration)
            .filter(
                Integration.user_id == current_user.id,
                Integration.external_id == artifact["id"],
                Integration.external_source == "CPI",
            )
            .first()
        )
        metrics = (
            metrics_by_artifact.get(artifact["symbolicName"])
            or metrics_by_artifact.get(artifact["name"])
            or {"has_data": False}
        )
        endpoints = connector.get_integration_endpoints(artifact["id"]) if metrics["has_data"] else []

        integration_data = convert_cpi_to_integration(artifact, endpoints)
        integration_data["user_id"] = current_user.id
        if existing and existing.target_system and integration_data["target_system"] == "Unknown":
            integration_data["target_system"] = existing.target_system

        if metrics["has_data"]:
            score, criticality = compute_score_and_criticality(
                metrics["total_messages"],
                metrics["error_rate"],
                integration_data["business_weight"],
            )
            integration_data.update(
                {
                    "monthly_volume": metrics["total_messages"],
                    "error_count": metrics["failed"],
                    "error_rate": round(metrics["error_rate"], 4),
                    "avg_processing_time": round(metrics["avg_time"], 2),
                    "score": score,
                    "criticality": criticality,
                }
            )
        elif existing:
            integration_data.update(
                {
                    "monthly_volume": existing.monthly_volume,
                    "error_count": existing.error_count,
                    "error_rate": existing.error_rate,
                    "avg_processing_time": existing.avg_processing_time,
                    "score": existing.score,
                    "criticality": existing.criticality,
                }
            )

        if existing:
            for key, value in integration_data.items():
                setattr(existing, key, value)
            existing.last_synced = datetime.utcnow()
        else:
            integration_data["last_synced"] = datetime.utcnow()
            db.add(Integration(**integration_data))

        total_synced += 1
        if index % 100 == 0:
            db.commit()

    if payload.reset:
        db.query(Integration).filter(
            Integration.user_id == current_user.id,
            Integration.external_source == "CPI",
            ~Integration.external_id.in_(seen_external_ids),
        ).delete(synchronize_session=False)

    deduplicate_cpi_integrations(db, current_user.id)
    db.commit()
    return {
        "message": "Sincronização CPI concluída",
        "total_synced": total_synced,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/")
def get_dashboard():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")
