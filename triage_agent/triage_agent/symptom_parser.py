from typing import List, Optional, Tuple
import re
from .schemas import PatientQuery, ParsedSymptom

SNOMED_DB = {
    "chest pain": {"snomed": "29857009", "icd10": "R07.9"},
    "fever": {"snomed": "386661006", "icd10": "R50.9"},
    "rash": {"snomed": "271807003", "icd10": "R21"},
    "headache": {"snomed": "25064002", "icd10": "R51"},
    "cough": {"snomed": "49727002", "icd10": "R05"},
}

def _map_to_ontology(text: str) -> Optional[Tuple[str, str, str]]:
    t = text.lower()
    for k, v in SNOMED_DB.items():
        if re.search(rf"\b{k}\b", t):
            return (k, v["snomed"], v["icd10"])
    return None

def parse_and_normalize(q: PatientQuery) -> List[ParsedSymptom]:
    candidates = re.split(r"[,;、，。；\s]+", q.text)
    out=[]
    for c in candidates:
        if len(c)<2: continue
        m=_map_to_ontology(c)
        if m:
            term,snomed,icd10=m
            out.append(ParsedSymptom(term=term,code=snomed,modifiers=[icd10]))
        else:
            out.append(ParsedSymptom(term=c,code=None))
    return out or [ParsedSymptom(term="unspecified",code=None)]