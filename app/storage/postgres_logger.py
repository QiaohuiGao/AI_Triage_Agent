from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.config import POSTGRES_URL
from loguru import logger
import json
from pydantic import BaseModel

engine = create_engine(POSTGRES_URL, pool_pre_ping=True, future=True)

def init_table():
    ddl = '''
    CREATE TABLE IF NOT EXISTS triage_logs (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP DEFAULT NOW(),
        patient_text TEXT,
        lang VARCHAR(8),
        output JSONB
    );
    '''
    try:
        with engine.begin() as conn:
            conn.execute(text(ddl))
    except SQLAlchemyError as e:
        logger.warning(f"DB init failed: {e}")

def _safe_json(o):
    if isinstance(o, BaseModel):
        return o.model_dump()
    elif isinstance(o, list):
        return [_safe_json(i) for i in o]
    elif isinstance(o, dict):
        return {k: _safe_json(v) for k, v in o.items()}
    else:
        return o

def log_request(patient: dict, result: dict):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO triage_logs (patient_text, lang, output) VALUES (:t, :l, :o)"),
                {"t": patient.get("text",""), "l": patient.get("lang","en"), "o": json.dumps(_safe_json(result))}
            )
    except SQLAlchemyError as e:
        logger.warning(f"DB log failed: {e}")
