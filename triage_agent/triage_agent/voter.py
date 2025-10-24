from typing import List,Dict
from statistics import mean,pstdev
from .schemas import Hypothesis,VoteResult

def confidence_voting(runs:List[List[Hypothesis]])->VoteResult:
    if not runs: return VoteResult([],0.0)
    conf_map:Dict[str,List[float]]={}
    for run in runs:
        for h in run:
            conf_map.setdefault(h.condition.lower(),[]).append(h.confidence)
    finals=[]
    for cond,vals in conf_map.items():
        avg,sd=mean(vals),pstdev(vals) if len(vals)>1 else 0.0
        stability=1/(1+sd)
        finals.append(Hypothesis(cond.title(),"Aggregated runs",round(avg*stability,3),[]))
    finals.sort(key=lambda x:-x.confidence)
    top=finals[0].condition.lower() if finals else ""
    agree=sum(any(top==h.condition.lower() for h in run) for run in runs)/len(runs)
    return VoteResult(finals[:3],round(agree,3))