from typing import List
import re,random
from .schemas import ParsedSymptom, RetrievalDoc, Hypothesis
from .retriever import retrieve_context

def _llm_reason(prompt:str)->str:
    p=prompt.lower()
    if "chest pain" in p: return "[Search: chest pain guideline]"
    if "rash" in p: return "[Search: rash causes]"
    return "[Search: general symptom triage]"

def _llm_reflect(ctx:str)->str:
    c=ctx.lower()
    if "angina" in c: return "angina"
    if "dermatitis" in c: return "dermatitis"
    return "unspecified"

def generate_hypotheses(symptoms:List[ParsedSymptom],ctx:List[RetrievalDoc])->List[Hypothesis]:
    query=", ".join([s.term for s in symptoms])
    thought=_llm_reason(query)
    m=re.search(r"\[Search:(.*?)\]",thought)
    search_q=m.group(1).strip() if m else query
    docs=retrieve_context(search_q)
    reflection=_llm_reflect(" ".join(d.text for d in docs[:3]))
    if "angina" in reflection:
        return [Hypothesis("Angina","Reflect supports angina",0.7,["radiating pain","shortness of breath"])]
    if "dermatitis" in reflection:
        return [Hypothesis("Allergic dermatitis","Reflect supports dermatitis",0.6,[])]
    return [Hypothesis("Unspecified","Low evidence",0.4,[])]