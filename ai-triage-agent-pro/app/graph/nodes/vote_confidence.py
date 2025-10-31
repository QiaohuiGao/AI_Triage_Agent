from typing import List, Dict, Any
from app.schemas import GraphState
def vote_confidence(state: dict) -> dict:
    """
    Aggregate reasoning runs to compute mean confidence and agreement stability.
    """
    runs: List[Dict[str, Any]] = getattr(state, "reasoning_runs", []) or []
    if not runs:
        state.vote_result = {"avg_confidence": 0, "agreement": 0, "stability": 1.0}
        return state

    confidences = [r.get("confidence", 0) for r in runs]
    avg = sum(confidences) / len(confidences)
    agreement = len(set(r.get("condition") for r in runs)) / len(runs)
    st = max(0.0001, (max(confidences) - min(confidences)))

    state.vote_result = {
        "avg_confidence": round(avg, 2),
        "agreement": round(1.0 - agreement, 2),
        "stability": round(1.0 / (1.0 + st), 2)
    }
    return state
