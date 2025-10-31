from typing import List
from app.schemas import RetrievalDoc
from app.config import PINECONE_SYMPTOM_INDEX, PINECONE_CONDITION_INDEX, PINECONE_CAREPATH_INDEX
from loguru import logger

def retrieve_multi(query: str, k: int = 5) -> List[RetrievalDoc]:
    logger.info(f"[Retriever] Query='{query}' using Pinecone indexes: "
                f"{PINECONE_SYMPTOM_INDEX}/{PINECONE_CONDITION_INDEX}/{PINECONE_CAREPATH_INDEX}")
    fake = [
        RetrievalDoc(level="symptom", id="S1", score=0.9, text="Chest pain red flags include pressure, radiation...", source="symptom_kb"),
        RetrievalDoc(level="condition", id="C1", score=0.86, text="Angina presents as exertional chest pressure...", source="condition_kb"),
        RetrievalDoc(level="carepath", id="P1", score=0.8, text="Cardiology handles suspected ischemic chest pain; ER for red flags.", source="carepath_kb"),
    ]
    return fake[:k]
