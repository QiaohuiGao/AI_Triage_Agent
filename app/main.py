"""
FastAPI 应用主入口 (main.py)
============================
本模块是 AI 分诊代理服务的入口点，提供：
- FastAPI RESTful API 服务
- 分诊请求处理端点 (/triage)
- Prometheus 监控指标端点 (/metrics)
- 请求日志持久化到 PostgreSQL
- 错误处理和响应序列化

v2.0 更新：
- 支持 ESI 五级分诊
- 支持生命体征输入
- 支持动态追问
- 添加 CORS 支持前端调用

主要流程：
1. 接收患者症状描述（可选包含生命体征）
2. 通过 LangGraph v2.0 执行分诊推理流程
3. 返回 ESI 等级、科室建议、红旗警告
4. 记录请求和结果到数据库
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app
from app.graph.triage_graph import build_triage_graph
from app.schemas import GraphState
from app.monitoring.prometheus_metrics import triage_latency, triage_success, triage_errors
from app.storage.postgres_logger import init_table, log_request
from loguru import logger
from pydantic import BaseModel
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import os

# 强制加载项目根目录的 .env
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=env_path)

# 检查是否加载成功（仅调试用，可安全保留）
key = os.getenv("OPENAI_API_KEY")
if key:
    print(f"✅ OPENAI_API_KEY loaded successfully: {key[:12]}...")
else:
    print("❌ OPENAI_API_KEY not found. Please check .env or path.") 

# ========== FastAPI 应用初始化 ==========
app = FastAPI(
    title="AI Triage Agent v2.0",
    description="ESI-based medical triage with Neo4j graph reasoning",
    version="2.0.0"
)

# ========== CORS 配置 ==========
# 允许前端跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 Prometheus 指标端点，用于监控服务健康状态和性能指标
app.mount("/metrics", make_asgi_app())

# 挂载静态文件目录（前端）
try:
    frontend_dir = os.path.join(BASE_DIR, "frontend")
    if os.path.exists(frontend_dir):
        app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
except Exception as e:
    logger.warning(f"Could not mount frontend static files: {e}")

# ========== LangGraph 图构建和编译 ==========
# 构建分诊推理图并编译为可执行状态
# 图包含以下节点：ParseSymptom -> RetrieveDocs -> ReasonReflect -> VoteConfidence -> FallbackRoute
graph = build_triage_graph().compile()

# ========== 数据库初始化 ==========
# 初始化 PostgreSQL 日志表（如果不存在则创建）
init_table()

# ========== 请求模型 (v2.0) ==========
class TriageRequest(BaseModel):
    """分诊请求模型"""
    text: str                                    # 患者症状描述
    lang: str = "en"                             # 语言代码
    metadata: Optional[Dict[str, Any]] = None    # 可选元数据
    vitals: Optional[Dict[str, Any]] = None      # v2.0: 生命体征
    clarification_response: Optional[str] = None # v2.0: 追问回答


# ========== API 端点定义 ==========
@app.get("/")
def root():
    """根路径 - 返回 API 信息"""
    return {
        "service": "AI Triage Agent",
        "version": "2.0.0",
        "status": "online",
        "endpoints": {
            "triage": "POST /triage",
            "health": "GET /health",
            "frontend": "GET /static/index.html"
        }
    }


@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "healthy", "version": "2.0.0"}


@app.post("/triage")
def triage_endpoint(request: TriageRequest):
    """
    分诊请求处理端点 (v2.0)

    接收患者症状描述（可选包含生命体征），执行 AI 分诊推理，
    返回 ESI 等级、科室建议和紧急程度。

    请求格式：
        {
            "text": "患者症状描述",
            "lang": "语言代码（默认en）",
            "metadata": {},  # 可选元数据
            "vitals": {      # 可选生命体征
                "hr": 80,
                "bp": "120/80",
                "spo2": 98,
                "temp": 36.5,
                "rr": 16
            },
            "clarification_response": "Yes, the pain radiates..."  # 追问回答
        }

    响应格式：
        {
            "esi_level": 2,
            "esi_assessment": {...},
            "final_output": {
                "suggested_department": "Emergency",
                "urgency": "ER",
                "esi_level": 2,
                "confidence": 0.95,
                "final_conditions": [...],
                "rationale": "...",
                "red_flags": [...],
                "evidence": [...]
            },
            "entities": [...],
            "red_flags": [...],
            "clarification_questions": [...],  # 如果需要追问
            "needs_clarification": false
        }
    """
    try:
        # 构建患者输入
        patient_input = {
            "text": request.text,
            "lang": request.lang,
            "metadata": request.metadata
        }

        # 构建初始状态
        initial_state = GraphState(
            patient_input=patient_input,
            vitals=request.vitals,
            clarification_response=request.clarification_response
        )

        # 执行 LangGraph v2.0 推理流程
        result = graph.invoke(initial_state)

        # ========== 序列化转换 ==========
        def _to_json(o):
            if isinstance(o, BaseModel):
                return o.model_dump()
            elif isinstance(o, list):
                return [_to_json(i) for i in o]
            elif isinstance(o, dict):
                return {k: _to_json(v) for k, v in o.items()}
            else:
                return o

        # 构建响应
        response = {
            "esi_level": result.get("esi_level"),
            "esi_assessment": _to_json(result.get("esi_assessment")),
            "final_output": _to_json(result.get("final_output")),
            "entities": _to_json(result.get("entities")),
            "red_flags": result.get("red_flags"),
            "graph_context": _to_json(result.get("graph_context")) if result.get("graph_context") else None,
            "needs_clarification": result.get("needs_clarification", False),
            "clarification_questions": result.get("clarification_questions"),
        }

        # ========== 日志记录 ==========
        log_request(patient_input, response.get("final_output", response))

        return JSONResponse(response)

    except Exception as e:
        logger.error(f"Triage endpoint error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {"error": "internal_error", "detail": str(e)},
            status_code=500
        )


# ========== 兼容旧版 API ==========
@app.post("/triage/v1")
def triage_v1_endpoint(patient: dict):
    """
    v1.0 兼容端点 - 使用旧版简单格式

    保留向后兼容性，使用 v1.0 的响应格式
    """
    try:
        result = graph.invoke({"patient_input": patient})
        output = result.get("final_output", result)

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
        logger.error(f"Triage v1 endpoint error: {e}")
        return JSONResponse({"error": "internal_error"}, status_code=500)
