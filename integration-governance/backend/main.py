from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, Optional
import smtplib
from email.mime.text import MIMEText

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.collector import calculate_score, classify
from backend.cpi_connector import CPIConnector, convert_cpi_to_integration
from backend.database import Base, SessionLocal, engine, sync_schema
from backend.models import AlertSettings, CPIEnvironment, Favorite, Integration, SyncSchedule, User, UserSession
from backend.schemas import (
    AlertItem,
    AlertResponse,
    AlertSettingsRead,
    AlertSettingsRequest,
    CPIEnvironmentRead,
    CPIEnvironmentRequest,
    CPISettingsRequest,
    CPISettingsResponse,
    FavoriteRead,
    IntegrationRead,
    LoginRequest,
    PaginatedIntegrationsResponse,
    RegisterRequest,
    SummaryResponse,
    SyncCPIRequest,
    SyncScheduleRead,
    SyncScheduleRequest,
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

scheduler = BackgroundScheduler()


def _run_auto_sync_for_user(user_id: int):
    """Called by APScheduler: syncs CPI for a user and sends email alerts if configured."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        decrypted = decrypt_secret(user.cpi_password_encrypted)
        if not all([user.cpi_host, user.cpi_username, decrypted, user.cpi_tenant_id]):
            return
        connector = CPIConnector(
            host=user.cpi_host,
            username=user.cpi_username,
            password=decrypted,
            tenant_id=user.cpi_tenant_id,
        )
        if not connector.health_check():
            return
        _do_sync(connector, db, user, reset=False, include_mpl=True, message_limit=100)
        schedule = db.query(SyncSchedule).filter(SyncSchedule.user_id == user_id).first()
        if schedule:
            schedule.last_run = datetime.utcnow()
            db.commit()
    except Exception:
        pass
    finally:
        db.close()


def _reload_scheduler():
    """Rebuild scheduler jobs from DB."""
    for job in scheduler.get_jobs():
        job.remove()
    db = SessionLocal()
    try:
        schedules = db.query(SyncSchedule).filter(SyncSchedule.enabled == 1).all()
        for s in schedules:
            scheduler.add_job(
                _run_auto_sync_for_user,
                "cron",
                hour=s.hour,
                minute=0,
                args=[s.user_id],
                id=f"sync_user_{s.user_id}",
                replace_existing=True,
            )
    finally:
        db.close()


def _send_alert_email(settings: AlertSettings, violations: list):
    """Send email alert via SMTP when threshold violations are found."""
    if not settings.enabled or not settings.email_to or not settings.smtp_host:
        return
    try:
        smtp_password = decrypt_secret(settings.smtp_password_encrypted) if settings.smtp_password_encrypted else ""
        body = "GDEP — Alertas de Integrações CPI\n\n"
        for v in violations:
            body += f"• {v}\n"
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"[GDEP] {len(violations)} alerta(s) de integração"
        msg["From"] = settings.smtp_user or "gdep@noreply"
        msg["To"] = settings.email_to
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            if settings.smtp_port in (587, 465):
                smtp.starttls()
            if settings.smtp_user and smtp_password:
                smtp.login(settings.smtp_user, smtp_password)
            smtp.sendmail(msg["From"], [settings.email_to], msg.as_string())
    except Exception:
        pass


@app.on_event("startup")
def startup_event():
    _reload_scheduler()
    scheduler.start()


@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown(wait=False)

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

    total_synced = _do_sync(connector, db, current_user, payload.reset, payload.include_mpl, payload.message_limit)

    # Send email alerts if configured
    alert_settings = db.query(AlertSettings).filter(AlertSettings.user_id == current_user.id).first()
    if alert_settings and alert_settings.enabled:
        violations = _collect_violations(db, current_user.id, alert_settings)
        if violations:
            _send_alert_email(alert_settings, violations)

    return {
        "message": "Sincronização CPI concluída",
        "total_synced": total_synced,
        "timestamp": datetime.utcnow().isoformat(),
    }


def _do_sync(connector: CPIConnector, db: Session, user: User, reset: bool, include_mpl: bool, message_limit: int) -> int:
    """
    Sync strategy: MPL-primary.

    1. Fetch bulk MessageProcessingLogs metrics (grouped by artifact).
    2. For every artifact that has REAL message data → create/update Integration.
    3. Also fetch artifacts from the Participant API to discover flows with no recent
       MPL messages (deployed but idle). Those are upserted with zero metrics.
    4. Use Sender/Receiver from MPL as source_system/target_system when available.
    """
    mpl_limit = max(message_limit * 100, 2000)
    bulk_metrics = connector.get_metrics_by_artifact(limit=mpl_limit) if include_mpl else {}

    # Deduplicate: keep only ONE entry per canonical artifact_id
    seen_canonical: set = set()
    canonical_metrics: Dict[str, Dict] = {}
    for key, m in bulk_metrics.items():
        flow_name = m.get("integration_flow_name") or key
        artifact_name = m.get("artifact_name") or key
        # canonical key = artifact_id (first non-null from message)
        canonical = flow_name  # flow_name == artifact_id in CPI MPL
        if canonical not in seen_canonical:
            seen_canonical.add(canonical)
            canonical_metrics[canonical] = m

    total_synced = 0
    seen_external_ids: set = set()

    # ── PASS 1: integrations with real MPL data ──────────────────────────────
    for canonical_id, metrics in canonical_metrics.items():
        if not metrics.get("has_data"):
            continue

        seen_external_ids.add(canonical_id)
        existing = (
            db.query(Integration)
            .filter(
                Integration.user_id == user.id,
                Integration.external_id == canonical_id,
                Integration.external_source == "CPI",
            )
            .first()
        )

        display_name = metrics.get("artifact_name") or metrics.get("integration_flow_name") or canonical_id
        source_system = metrics.get("sender") or "SAP CPI"
        target_system = metrics.get("receiver") or (existing.target_system if existing else "Unknown")

        score, criticality = compute_score_and_criticality(
            metrics["total_messages"],
            metrics["error_rate"],
            5,  # default business_weight
        )

        integration_data = {
            "user_id": user.id,
            "name": display_name,
            "platform": "CPI",
            "source_system": source_system,
            "target_system": target_system,
            "monthly_volume": metrics["total_messages"],
            "error_count": metrics["failed"],
            "error_rate": round(metrics["error_rate"], 4),
            "avg_processing_time": round(metrics["avg_time"], 2),
            "business_weight": existing.business_weight if existing else 5,
            "score": score,
            "criticality": criticality,
            "external_id": canonical_id,
            "external_source": "CPI",
        }

        if existing:
            for key, value in integration_data.items():
                setattr(existing, key, value)
            existing.last_synced = datetime.utcnow()
        else:
            integration_data["last_synced"] = datetime.utcnow()
            db.add(Integration(**integration_data))

        total_synced += 1

    db.commit()

    # ── PASS 2: Participant API artifacts without MPL data (idle/new flows) ───
    try:
        artifacts = connector.get_integration_artifacts()
    except Exception as e:
        logger.warning(f"Could not fetch Participant API artifacts: {e}")
        artifacts = []

    for artifact in artifacts:
        artifact_id = artifact.get("id")
        if not artifact_id:
            continue

        # Try to match with already-synced MPL data via all possible keys
        metrics = (
            bulk_metrics.get(artifact_id)
            or bulk_metrics.get(artifact.get("symbolicName"))
            or bulk_metrics.get(artifact.get("name"))
            or {}
        )

        if metrics.get("has_data"):
            # Already handled in pass 1 (the canonical_id might differ slightly)
            canonical_id = metrics.get("integration_flow_name") or artifact_id
            seen_external_ids.add(canonical_id)
            seen_external_ids.add(artifact_id)
            continue

        # Targeted fallback removed — bulk MPL (30 days) already covers all active flows.
        # Individual per-artifact queries cause 700+ HTTP calls and timeout the sync endpoint.

        seen_external_ids.add(artifact_id)
        existing = (
            db.query(Integration)
            .filter(
                Integration.user_id == user.id,
                Integration.external_id == artifact_id,
                Integration.external_source == "CPI",
            )
            .first()
        )

        endpoints = connector.get_integration_endpoints(artifact_id) if metrics.get("has_data") else []
        integration_data = convert_cpi_to_integration(artifact, endpoints)
        integration_data["user_id"] = user.id

        if existing and existing.target_system and integration_data["target_system"] == "Unknown":
            integration_data["target_system"] = existing.target_system

        if metrics.get("has_data"):
            source_sys = metrics.get("sender") or integration_data["source_system"]
            target_sys = metrics.get("receiver") or integration_data["target_system"]
            score, criticality = compute_score_and_criticality(
                metrics["total_messages"],
                metrics["error_rate"],
                integration_data["business_weight"],
            )
            integration_data.update(
                {
                    "source_system": source_sys,
                    "target_system": target_sys,
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

    if reset:
        db.query(Integration).filter(
            Integration.user_id == user.id,
            Integration.external_source == "CPI",
            ~Integration.external_id.in_(seen_external_ids),
        ).delete(synchronize_session=False)

    deduplicate_cpi_integrations(db, user.id)
    db.commit()
    return total_synced


def _collect_violations(db: Session, user_id: int, settings: AlertSettings) -> list:
    violations = []
    integrations = db.query(Integration).filter(Integration.user_id == user_id).all()
    for i in integrations:
        if i.error_rate > settings.error_rate_threshold:
            violations.append(
                f"{i.name}: taxa de erro {i.error_rate * 100:.1f}% > limite {settings.error_rate_threshold * 100:.1f}%"
            )
        if i.avg_processing_time > settings.processing_time_threshold:
            violations.append(
                f"{i.name}: tempo médio {i.avg_processing_time:.0f} ms > limite {settings.processing_time_threshold:.0f} ms"
            )
    return violations


# --- CPI Environments ---

@app.get("/me/cpi-environments", response_model=list[CPIEnvironmentRead])
def list_environments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(CPIEnvironment).filter(CPIEnvironment.user_id == current_user.id).all()


@app.post("/me/cpi-environments", response_model=CPIEnvironmentRead)
def create_environment(
    payload: CPIEnvironmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    env = CPIEnvironment(
        user_id=current_user.id,
        name=payload.name.strip(),
        environment_type=payload.environment_type,
        cpi_host=payload.cpi_host.strip(),
        cpi_username=payload.cpi_username.strip(),
        cpi_password_encrypted=encrypt_secret(payload.cpi_password),
        cpi_tenant_id=payload.cpi_tenant_id.strip(),
        is_active=0,
        created_at=datetime.utcnow(),
    )
    db.add(env)
    db.commit()
    db.refresh(env)
    return env


@app.put("/me/cpi-environments/{env_id}/activate")
def activate_environment(
    env_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    env = db.query(CPIEnvironment).filter(CPIEnvironment.id == env_id, CPIEnvironment.user_id == current_user.id).first()
    if not env:
        raise HTTPException(status_code=404, detail="Ambiente não encontrado.")
    # Deactivate all, activate selected
    db.query(CPIEnvironment).filter(CPIEnvironment.user_id == current_user.id).update({"is_active": 0})
    env.is_active = 1
    # Apply to user's main CPI settings
    current_user.cpi_host = env.cpi_host
    current_user.cpi_username = env.cpi_username
    current_user.cpi_password_encrypted = env.cpi_password_encrypted
    current_user.cpi_tenant_id = env.cpi_tenant_id
    current_user.settings_updated_at = datetime.utcnow()
    db.commit()
    return {"message": f"Ambiente '{env.name}' ativado."}


@app.delete("/me/cpi-environments/{env_id}")
def delete_environment(
    env_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    env = db.query(CPIEnvironment).filter(CPIEnvironment.id == env_id, CPIEnvironment.user_id == current_user.id).first()
    if not env:
        raise HTTPException(status_code=404, detail="Ambiente não encontrado.")
    db.delete(env)
    db.commit()
    return {"message": "Ambiente removido."}


# --- Favorites ---

@app.get("/me/favorites", response_model=list[FavoriteRead])
def list_favorites(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Favorite).filter(Favorite.user_id == current_user.id).all()


@app.post("/integrations/{integration_id}/favorite")
def toggle_favorite(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    integration = db.query(Integration).filter(Integration.id == integration_id, Integration.user_id == current_user.id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integração não encontrada.")
    existing = db.query(Favorite).filter(Favorite.user_id == current_user.id, Favorite.integration_id == integration_id).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"favorited": False}
    db.add(Favorite(user_id=current_user.id, integration_id=integration_id, created_at=datetime.utcnow()))
    db.commit()
    return {"favorited": True}


# --- Alert Settings ---

@app.get("/me/alert-settings", response_model=AlertSettingsRead)
def get_alert_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    settings = db.query(AlertSettings).filter(AlertSettings.user_id == current_user.id).first()
    if not settings:
        return AlertSettingsRead(
            id=0, enabled=0, error_rate_threshold=0.05, processing_time_threshold=1000.0,
            smtp_port=587, has_smtp_password=False
        )
    return AlertSettingsRead(
        id=settings.id,
        enabled=settings.enabled,
        email_to=settings.email_to,
        error_rate_threshold=settings.error_rate_threshold,
        processing_time_threshold=settings.processing_time_threshold,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        has_smtp_password=bool(settings.smtp_password_encrypted),
    )


@app.put("/me/alert-settings", response_model=AlertSettingsRead)
def update_alert_settings(
    payload: AlertSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = db.query(AlertSettings).filter(AlertSettings.user_id == current_user.id).first()
    if not settings:
        settings = AlertSettings(user_id=current_user.id, created_at=datetime.utcnow())
        db.add(settings)
    settings.enabled = 1 if payload.enabled else 0
    settings.email_to = payload.email_to
    settings.error_rate_threshold = payload.error_rate_threshold
    settings.processing_time_threshold = payload.processing_time_threshold
    settings.smtp_host = payload.smtp_host
    settings.smtp_port = payload.smtp_port
    settings.smtp_user = payload.smtp_user
    if payload.smtp_password:
        settings.smtp_password_encrypted = encrypt_secret(payload.smtp_password)
    db.commit()
    db.refresh(settings)
    return AlertSettingsRead(
        id=settings.id,
        enabled=settings.enabled,
        email_to=settings.email_to,
        error_rate_threshold=settings.error_rate_threshold,
        processing_time_threshold=settings.processing_time_threshold,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        has_smtp_password=bool(settings.smtp_password_encrypted),
    )


# --- Sync Schedule ---

@app.get("/me/sync-schedule", response_model=SyncScheduleRead)
def get_sync_schedule(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    schedule = db.query(SyncSchedule).filter(SyncSchedule.user_id == current_user.id).first()
    if not schedule:
        return SyncScheduleRead(id=0, enabled=0, hour=6)
    return schedule


@app.put("/me/sync-schedule", response_model=SyncScheduleRead)
def update_sync_schedule(
    payload: SyncScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schedule = db.query(SyncSchedule).filter(SyncSchedule.user_id == current_user.id).first()
    if not schedule:
        schedule = SyncSchedule(user_id=current_user.id, created_at=datetime.utcnow())
        db.add(schedule)
    schedule.enabled = 1 if payload.enabled else 0
    schedule.hour = payload.hour
    db.commit()
    db.refresh(schedule)
    _reload_scheduler()
    return schedule


@app.get("/")
def get_dashboard():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")
