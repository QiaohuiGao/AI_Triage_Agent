from fastapi import FastAPI
from triage_agent.schemas import PatientQuery,TriageOutput
from triage_agent.pipeline import triage_once

app=FastAPI(title="AI Triage Agent")

@app.post("/triage",response_model=TriageOutput)
def triage_api(q:PatientQuery):
    return triage_once(q)