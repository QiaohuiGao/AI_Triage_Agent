"""
PostgreSQL 日志记录模块 (postgres_logger.py)
===========================================
本模块负责将分诊请求和结果持久化存储到 PostgreSQL 数据库。

功能：
- 初始化数据库表（triage_logs）
- 记录分诊请求（患者输入和分诊结果）
- 支持 JSONB 格式存储复杂的嵌套数据结构
- 提供错误处理和日志记录

用途：
- 审计和合规性：记录所有分诊决策
- 分析和优化：用于分析分诊准确性和性能
- 调试和排查：追踪问题请求和结果
- 数据挖掘：用于模型训练和优化

数据库表结构：
- id: 主键（自增）
- created_at: 创建时间戳（自动填充）
- patient_text: 患者症状描述文本
- lang: 语言代码
- output: 分诊结果（JSONB 格式）
"""

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.config import POSTGRES_URL
from loguru import logger
import json
from pydantic import BaseModel

# ========== 数据库引擎初始化 ==========
# 创建 SQLAlchemy 数据库引擎，用于连接 PostgreSQL
# pool_pre_ping=True: 连接池预检，确保连接可用
# future=True: 使用 SQLAlchemy 2.0 风格的 API
engine = create_engine(POSTGRES_URL, pool_pre_ping=True, future=True)

def init_table():
    """
    初始化数据库表
    
    创建 triage_logs 表（如果不存在）。
    表结构：
    - id: 主键（自增）
    - created_at: 创建时间戳（默认当前时间）
    - patient_text: 患者症状描述文本
    - lang: 语言代码（最大8字符）
    - output: 分诊结果（JSONB 格式，支持嵌套数据结构）
    
    如果表已存在，则不执行任何操作。
    """
    # ========== DDL 语句 ==========
    # 定义 CREATE TABLE IF NOT EXISTS 语句
    ddl = '''
    CREATE TABLE IF NOT EXISTS triage_logs (
        id SERIAL PRIMARY KEY,                           -- 主键（自增）
        created_at TIMESTAMP DEFAULT NOW(),              -- 创建时间戳（自动填充）
        patient_text TEXT,                                -- 患者症状描述文本
        lang VARCHAR(8),                                 -- 语言代码（最大8字符）
        output JSONB                                     -- 分诊结果（JSONB 格式）
    );
    '''
    
    try:
        # 使用事务执行 DDL 语句
        with engine.begin() as conn:
            conn.execute(text(ddl))
    except SQLAlchemyError as e:
        # 如果初始化失败，记录警告日志但不抛出异常
        # 这样应用可以继续运行，只是不会记录日志
        logger.warning(f"DB init failed: {e}")

def _safe_json(o):
    """
    安全地将对象转换为 JSON 可序列化的格式
    
    递归处理嵌套的数据结构，将 Pydantic 模型转换为字典。
    这是必要的，因为 FastAPI 返回的响应可能包含 Pydantic 对象，
    而 JSON 序列化需要纯字典格式。
    
    参数:
        o: 要转换的对象（可以是 Pydantic 模型、字典、列表或基本类型）
    
    返回:
        JSON 可序列化的对象（字典、列表或基本类型）
    """
    if isinstance(o, BaseModel):
        # Pydantic 模型转为字典
        return o.model_dump()
    elif isinstance(o, list):
        # 递归处理列表中的每个元素
        return [_safe_json(i) for i in o]
    elif isinstance(o, dict):
        # 递归处理字典中的每个值
        return {k: _safe_json(v) for k, v in o.items()}
    else:
        # 基本类型（str, int, float, bool, None）直接返回
        return o

def log_request(patient: dict, result: dict):
    """
    记录分诊请求和结果到数据库
    
    将患者输入和分诊结果插入到 triage_logs 表中。
    使用参数化查询防止 SQL 注入，并使用事务确保数据一致性。
    
    参数:
        patient: 患者输入字典，包含 text 和 lang 字段
        result: 分诊结果字典，包含科室建议、置信度等信息
    
    如果记录失败，记录警告日志但不抛出异常，确保不影响主流程。
    """
    try:
        # 使用事务执行插入操作
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO triage_logs (patient_text, lang, output) VALUES (:t, :l, :o)"),
                {
                    "t": patient.get("text", ""),                    # 患者症状描述文本
                    "l": patient.get("lang", "en"),                 # 语言代码（默认英语）
                    "o": json.dumps(_safe_json(result))             # 分诊结果（JSON 字符串）
                }
            )
    except SQLAlchemyError as e:
        # 如果记录失败，记录警告日志但不抛出异常
        # 这样分诊服务可以继续运行，只是不会记录日志
        logger.warning(f"DB log failed: {e}")
