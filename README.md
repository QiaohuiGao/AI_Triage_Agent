🏥 AI Triage Agent

An intelligent clinical triage system built with FastAPI, LangGraph, and PostgreSQL.
The agent processes patient complaints using language models, performs retrieval and reasoning, and outputs a safe, explainable routing decision for clinical departments.

⸻

🚀 Features
	•	🧠 Symptom understanding — parses and normalizes free-text patient input
	•	📚 Evidence retrieval — retrieves relevant clinical documents or guidelines
	•	🔎 Reasoning and reflection — multi-step reasoning with LangGraph nodes
	•	⚖️ Confidence voting — consensus and stability check across multiple reasoning runs
	•	🏥 Routing decision — recommends department and urgency level
	•	📊 PostgreSQL logging — logs triage requests and responses for analysis
	•	📈 Prometheus monitoring — track service metrics in production

⸻

🧩 Project Structure

⸻

⚙️ Installation

# 1️⃣ Clone the repo
git clone https://github.com/<your-username>/ai-triage-agent-pro.git
cd ai-triage-agent-pro

# 2️⃣ Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3️⃣ Install dependencies
pip install -r requirements.txt


⸻

🧠 Run Locally

# 1️⃣ Start PostgreSQL (Homebrew example)
brew services start postgresql

# 2️⃣ Create database
psql postgres
CREATE DATABASE triage;

# 3️⃣ Launch FastAPI server
.venv/bin/uvicorn app.main:app --reload --port 8080

Then open your browser at:
👉 http://127.0.0.1:8080/docs (interactive Swagger UI)

⸻

🧪 Example Request

curl -X POST http://127.0.0.1:8080/triage \
  -H "Content-Type: application/json" \
  -d '{"text": "I feel chest tightness and shortness of breath", "lang": "en"}'

✅ Example Response

{
  "suggested_department": "Emergency",
  "urgency": "ER",
  "confidence": 0.99,
  "agreement": 0.0,
  "final_conditions": [
    {"condition": "Undifferentiated complaint", "confidence": 0.0}
  ],
  "rationale": "Red-flag safety rule triggered.",
  "evidence": [
    {"level": "high", "text": "Clinical guideline for chest pain", "source": "mock_db"},
    {"level": "medium", "text": "Possible causes and treatment for shortness of breath", "source": "mock_db"}
  ]
}


⸻

🧰 Tech Stack
	•	Backend: FastAPI, LangGraph, Pydantic
	•	Database: PostgreSQL
	•	Observability: Prometheus, Grafana
	•	Deployment: Docker, Kubernetes (optional)
	•	Language: Python 3.11

⸻

🧑‍💻 Author

👩‍💻 Qiaohui (Bonnie) Gao
Research Engineer @ HMS & MGH | MS in CS @ Northeastern
🔗 LinkedIn￼ | GitHub￼

