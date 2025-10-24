from typing import List
from .schemas import RetrievalDoc,Hypothesis,RoutingDecision
from .config import CFG

def need_fallback(docs:List[RetrievalDoc],hyps:List[Hypothesis],agreement:float)->bool:
    doc_ok=len([d for d in docs if d.score>0.25])>=CFG.vector.min_hits
    hyp_ok=any(h.confidence>=CFG.th.low_conf for h in hyps)
    agree_ok=agreement>=CFG.th.min_agreement
    return not(doc_ok and hyp_ok and agree_ok)

def conservative_route(hyps:List[Hypothesis])->RoutingDecision:
    if not hyps: return RoutingDecision("Primary Care","moderate",0.4,["no-hypothesis"])
    top=hyps[0].condition.lower()
    if "angina" in top or "chest" in top:
        return RoutingDecision("Cardiology / Emergency","high",0.8,["fallback-high-risk"])
    return RoutingDecision("Primary Care","moderate",0.5,["fallback-general"])