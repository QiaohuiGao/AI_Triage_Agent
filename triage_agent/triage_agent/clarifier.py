from typing import List
from .schemas import Hypothesis, ClarifyingQuestion

def make_clarifying_questions(hyps:List[Hypothesis])->List[ClarifyingQuestion]:
    if not hyps: return []
    top=hyps[0].condition.lower()
    if "angina" in top or "chest" in top:
        return [ClarifyingQuestion("Is chest pain triggered by exertion?","Supports ischemic pattern",["Yes","No"]),
                ClarifyingQuestion("Do you feel pain radiating to arm or jaw?","Indicates cardiac risk",["Yes","No"])]
    if "dermatitis" in top or "rash" in top:
        return [ClarifyingQuestion("Is the rash itchy and linked to new product contact?","Supports contact dermatitis",["Yes","No"])]
    return []