from typing import List
from .schemas import PatientQuery,TriageOutput,Hypothesis,ClarifyingQuestion
from .symptom_parser import parse_and_normalize
from .retriever import retrieve_context
from .reasoner import generate_hypotheses
from .clarifier import make_clarifying_questions
from .voter import confidence_voting
from .router import route
from .fallback import need_fallback,conservative_route
from .config import CFG

def triage_once(q:PatientQuery)->TriageOutput:
    symptoms=parse_and_normalize(q)
    ctx=retrieve_context(q.text)
    runs=[generate_hypotheses(symptoms,ctx) for _ in range(CFG.llm.ensemble_runs)]
    vote=confidence_voting(runs)
    hyps=vote.final_conditions
    routing=route(hyps) if not need_fallback(ctx,hyps,vote.agreement) else conservative_route(hyps)
    msg=f"Based on {CFG.llm.ensemble_runs} reasoning runs (agreement={vote.agreement:.2f}), suggested: {routing.suggested_department}."
    return TriageOutput(likely_conditions=hyps,routing=routing,clarifying_questions=make_clarifying_questions(hyps),message=msg,raw_context_ids=[d.id for d in ctx])