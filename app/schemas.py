from pydantic import BaseModel, Field
from typing import List, Optional, Any,Dict

class PatientInput(BaseModel):
    text: str
    lang: str = Field(default="en")
    metadata: Optional[dict] = None

class RetrievalDoc(BaseModel):
    """
    Schema for documents retrieved from the vector store.
    """
    level: str
    id: str
    score: float
    text: str
    source: str

class ReasoningRun(BaseModel):
    hypothesis: str
    conditions: List[str]
    department: Optional[str]
    confidence: float
    evidence_ids: List[str]

class TriageOutput(BaseModel):
    suggested_department: str
    urgency: str
    confidence: float
    agreement: float
    final_conditions: List[dict]
    rationale: str
    evidence: List[RetrievalDoc]

class GraphState(BaseModel):
    """
    The core shared state passed across all LangGraph nodes.
    Each node reads or writes different subsets of this state.
    """
    patient_input: Dict[str, Any]
    entities: Optional[List[Dict[str, Any]]] = None
    retrieved_docs: Optional[List[RetrievalDoc]] = None
    reflection: Optional[Dict[str, Any]] = None      # 🧠 ReasonReflect adds this
    voting_result: Optional[Dict[str, Any]] = None   # 🧮 VoteConfidence adds this
    routing: Optional[Dict[str, Any]] = None         # 🧭 FallbackRoute adds this
    reasoning_runs: Optional[List[Dict[str, Any]]] = None
    final_output: Optional[Dict[str, Any]] = None
    vote_result: Optional[Dict[str, Any]] = None
    
