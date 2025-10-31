from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from app.graph.triage_graph import build_triage_graph
from app.monitoring.prometheus_metrics import triage_latency, triage_success, triage_errors
from app.storage.postgres_logger import init_table, log_request
from loguru import logger
from pydantic import BaseModel

app = FastAPI(title="AI Triage Agent (LangGraph)")
app.mount("/metrics", make_asgi_app())

graph = build_triage_graph().compile()
init_table()

@app.post("/triage")
def triage_endpoint(patient: dict):
    try:
        result = graph.invoke({"patient_input": patient})
        output = result.get("final_output", result)

        # ✅ 序列化转换：将所有 Pydantic 模型转为 dict
        def _to_json(o):
            if isinstance(o, BaseModel):
                return o.model_dump()
            elif isinstance(o, list):
                return [_to_json(i) for i in o]
            elif isinstance(o, dict):
                return {k: _to_json(v) for k, v in o.items()}
            else:
                return o

        output = _to_json(output)

        log_request(patient, output)
        return JSONResponse(output)

    except Exception as e:
        logger.error(f"{e}")
        return JSONResponse({"error": "internal_error"}, status_code=500)
