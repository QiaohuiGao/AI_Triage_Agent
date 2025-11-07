"""
FastAPI 应用主入口 (main.py)
============================
本模块是 AI 分诊代理服务的入口点，提供：
- FastAPI RESTful API 服务
- 分诊请求处理端点 (/triage)
- Prometheus 监控指标端点 (/metrics)
- 请求日志持久化到 PostgreSQL
- 错误处理和响应序列化

主要流程：
1. 接收患者症状描述
2. 通过 LangGraph 执行分诊推理流程
3. 记录请求和结果到数据库
4. 返回 JSON 格式的分诊建议
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from app.graph.triage_graph import build_triage_graph
from app.monitoring.prometheus_metrics import triage_latency, triage_success, triage_errors
from app.storage.postgres_logger import init_table, log_request
from loguru import logger
from pydantic import BaseModel
from dotenv import load_dotenv;
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
app = FastAPI(title="AI Triage Agent (LangGraph)")

# 挂载 Prometheus 指标端点，用于监控服务健康状态和性能指标
app.mount("/metrics", make_asgi_app())

# ========== LangGraph 图构建和编译 ==========
# 构建分诊推理图并编译为可执行状态
# 图包含以下节点：ParseSymptom -> RetrieveDocs -> ReasonReflect -> VoteConfidence -> FallbackRoute
graph = build_triage_graph().compile()

# ========== 数据库初始化 ==========
# 初始化 PostgreSQL 日志表（如果不存在则创建）
init_table()

# ========== API 端点定义 ==========
@app.post("/triage")
def triage_endpoint(patient: dict):
    """
    分诊请求处理端点
    
    接收患者症状描述，执行 AI 分诊推理，返回科室建议和紧急程度。
    
    请求格式：
        {
            "text": "患者症状描述",
            "lang": "语言代码（默认en）",
            "metadata": {}  # 可选元数据
        }
    
    响应格式：
        {
            "suggested_department": "建议科室",
            "urgency": "紧急程度（ER/Urgent/Routine）",
            "confidence": 0.xx,  # 置信度
            "agreement": 0.xx,   # 一致性
            "final_conditions": [],  # 可能的疾病
            "rationale": "推理依据",
            "evidence": []  # 检索到的医疗文档证据
        }
    """
    try:
        # 执行 LangGraph 推理流程
        # 输入：患者输入数据
        # 输出：包含 final_output 的完整状态
        result = graph.invoke({"patient_input": patient})
        
        # 提取最终输出，如果没有 final_output 则使用整个 result
        output = result.get("final_output", result)

        # ========== 序列化转换 ==========
        # 将 Pydantic 模型递归转换为 JSON 可序列化的字典
        # 这是因为 FastAPI 返回时需要纯字典格式，不能包含 Pydantic 对象
        def _to_json(o):
            if isinstance(o, BaseModel):
                return o.model_dump()  # Pydantic 模型转为字典
            elif isinstance(o, list):
                return [_to_json(i) for i in o]  # 递归处理列表
            elif isinstance(o, dict):
                return {k: _to_json(v) for k, v in o.items()}  # 递归处理字典
            else:
                return o  # 基本类型直接返回

        output = _to_json(output)

        # ========== 日志记录 ==========
        # 将请求和结果持久化到 PostgreSQL，用于后续分析和审计
        log_request(patient, output)
        
        # 返回 JSON 响应
        return JSONResponse(output)

    except Exception as e:
        # ========== 错误处理 ==========
        # 记录错误日志并返回 500 错误响应
        logger.error(f"Triage endpoint error: {e}")
        return JSONResponse({"error": "internal_error"}, status_code=500)
