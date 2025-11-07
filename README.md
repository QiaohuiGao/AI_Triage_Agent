# 🏥 AI Triage Agent (LangGraph + FastAPI)

This project implements a **production-grade AI Triage Agent** that routes patients to the appropriate medical departments based on their symptoms.  
It combines **LangGraph**, **LlamaIndex**, **Pinecone**, and **FastAPI** to perform retrieval, reasoning, and structured decision-making.

---

## 🚀 Features

- 🧠 **Graph-based AI reasoning** built with [LangGraph](https://github.com/langchain-ai/langgraph)
- 🔍 **Medical retrieval** using Pinecone + LlamaIndex
- ⚙️ **FastAPI RESTful service** with `/triage` endpoint
- 📊 **Monitoring** via Prometheus + Grafana
- 🗄️ **PostgreSQL logging** with async storage layer
- ☁️ **Deployment ready** for Docker, Kubernetes, and GitHub Actions CI/CD

---

## 🧩 Project Structure
ai-triage-agent-pro/
├── app/
│   ├── main.py                 # FastAPI entrypoint
│   ├── config.py               # global constants
│   ├── schemas.py              # GraphState, Pydantic models
│   ├── graph/
│   │   ├── triage_graph.py     # LangGraph node definitions
│   │   └── nodes/              # Each reasoning node (ParseSymptom, RetrieveDocs, etc.)
│   ├── storage/
│   │   └── postgres_logger.py  # PostgreSQL request logger
│   └── utils/                  # helper utilities
├── requirements.txt
├── Dockerfile
├── README.md
└── .gitignore---

## 🧠 Example Usage

### Run locally
```bash
.venv/bin/uvicorn app.main:app --reload --port 8080

Then test with:
curl -s -X POST http://127.0.0.1:8081/triage \
  -H "Content-Type: application/json" \
  -d '{ "text": "I feel chest tightness and shortness of breath", "lang": "en" }' | jq

Expected output:
{
  "suggested_department": "Emergency",
  "urgency": "ER",
  "confidence": 0.99,
  "agreement": 0.0,
  "final_conditions": [
    { "condition": "Undifferentiated complaint", "confidence": 0.0 }
  ],
  "rationale": "Red-flag safety rule triggered.",
  "evidence": [
    { "level": "high", "text": "Clinical guideline for chest pain" },
    { "level": "medium", "text": "Possible causes and treatment for shortness of breath" }
  ]
}
