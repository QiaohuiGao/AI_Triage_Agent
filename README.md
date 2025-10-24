# 🏥 AI Triage & Patient Guide Agent

## Overview
This project implements a modular **AI triage system** that helps patients describe their symptoms, understand probable conditions, and get routed to the right hospital department.

---

## 🧩 Architecture
Patient Input

↓
Symptom Parser (Ontology mapping: SNOMED/ICD)

↓
Multi-level Retrieval (Symptom / Condition / Care-path)

↓
ReAct Reasoning (Reason → Act → Reflect)

↓
Confidence Voting + Fallback Ensemble

↓
Routing & Department Recommendation

---

## 🚀 Quick Start
```bash
# 1️⃣ Install dependencies
pip install -r requirements.txt

# 2️⃣ Run API
uvicorn app:app --reload

# 3️⃣ Test API
curl -X POST http://127.0.0.1:8000/triage \
     -H "Content-Type: application/json" \
     -d '{"text": "I have chest pain and shortness of breath"}'
