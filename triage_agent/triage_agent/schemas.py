from typing import List, Optional, Dict, Literal
from pydantic import BaseModel

class PatientQuery(BaseModel):
    text: str
    age: Optional[int] = None
    sex: Optional[Literal["male","female","other"]] = None

class ParsedSymptom(BaseModel):
    term: str
    code: Optional[str]
    duration: Optional[str] = None
    severity: Optional[str] = None
    modifiers: List[str] = []

class RetrievalDoc(BaseModel):
    id: str
    text: str
    score: float
    meta: Dict[str, str] = {}

class Hypothesis(BaseModel):
    condition: str
    rationale: str
    confidence: float
    red_flags: List[str] = []

class ClarifyingQuestion(BaseModel):
    question: str
    expected_signal: str
    choices: Optional[List[str]] = None

class VoteResult(BaseModel):
    final_conditions: List[Hypothesis]
    agreement: float

class RoutingDecision(BaseModel):
    suggested_department: str
    urgency: Literal["low","moderate","high","emergent"]
    confidence: float
    evidence: List[str]

class TriageOutput(BaseModel):
    likely_conditions: List[Hypothesis]
    routing: RoutingDecision
    clarifying_questions: List[ClarifyingQuestion] = []
    message: str
    raw_context_ids: List[str] = []