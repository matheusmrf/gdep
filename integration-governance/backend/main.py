from fastapi import FastAPI
from backend.database import engine, Base, SessionLocal
from backend.models import Integration
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/integrations")
def get_integrations():
    db: Session = SessionLocal()
    integrations = db.query(Integration).all()
    db.close()
    return integrations
