from typing import List
from .schemas import Hypothesis,RoutingDecision

ROUTE_TABLE={"angina":("Cardiology","high"),"dermatitis":("Dermatology","low"),"unspecified":("Primary Care","moderate")}

def route(hyps:List[Hypothesis])->RoutingDecision:
    if not hyps: return RoutingDecision("Primary Care","moderate",0.4,["default"])
    for h in hyps:
        for k,(dept,urg) in ROUTE_TABLE.items():
            if k in h.condition.lower():
                return RoutingDecision(dept,urg,h.confidence,[f"route:{k}"])
    return RoutingDecision("Primary Care","moderate",hyps[0].confidence,[f"fallback:{hyps[0].condition}"])