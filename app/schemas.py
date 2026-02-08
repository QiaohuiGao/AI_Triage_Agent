"""
数据模型定义 (schemas.py)
=========================
本模块定义了项目中使用的所有 Pydantic 数据模型，包括：
- 输入数据模型（PatientInput）
- 检索文档模型（RetrievalDoc）
- 推理运行模型（ReasoningRun）
- 分诊输出模型（TriageOutput）
- 图状态模型（GraphState）- 这是 LangGraph 的核心状态容器

所有模型都使用 Pydantic 进行数据验证和类型检查。
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

# ========== 输入数据模型 ==========
class PatientInput(BaseModel):
    """
    患者输入数据模型
    
    表示从 API 接收到的患者症状描述请求。
    """
    text: str                    # 患者症状描述文本
    lang: str = Field(default="en")  # 语言代码，默认为英语
    metadata: Optional[dict] = None  # 可选的元数据信息

# ========== 检索文档模型 ==========
class RetrievedDoc(BaseModel):
    """
    检索文档模型
    
    表示从向量数据库（Pinecone）检索到的医疗知识文档。
    这些文档用于为 AI 推理提供医学证据支持。
    """
    level: str      # 文档级别：symptom（症状）/ condition（疾病）/ carepath（诊疗路径）
    id: str         # 文档唯一标识符
    score: float    # 相似度得分（0-1），越高表示与查询越相关
    text: str       # 文档文本内容
    source: str     # 文档来源标识（如 symptom_kb, condition_kb, carepath_kb）

# ========== 推理运行模型 ==========
class ReasoningRun(BaseModel):
    """
    推理运行模型
    
    表示一次完整的 AI 推理过程的结果，包括：
    - 假设的诊断
    - 可能的疾病列表
    - 建议的科室
    - 置信度
    - 使用的证据文档ID
    """
    hypothesis: str              # 推理假设/诊断假设
    conditions: List[str]        # 可能的疾病条件列表
    department: Optional[str]    # 建议的科室
    confidence: float            # 本次推理的置信度（0-1）
    evidence_ids: List[str]      # 使用的证据文档ID列表

# ========== 分诊输出模型 ==========
class TriageOutput(BaseModel):
    """
    分诊输出模型
    
    表示最终的分诊建议结果，返回给 API 调用者。
    这是整个分诊流程的最终输出。
    """
    suggested_department: str          # 建议的科室（如 Emergency, Cardiology, Primary Care）
    urgency: str                      # 紧急程度：ER（急诊）/ Urgent（紧急）/ Routine（常规）
    confidence: float                 # 整体置信度（0-1）
    agreement: float                  # 多个推理结果的一致性（0-1）
    final_conditions: List[dict]     # 最终可能的疾病列表，每个包含 condition 和 confidence
    rationale: str                    # 推理依据和说明
    evidence: List[RetrievedDoc]      # 使用的医疗文档证据列表

# ========== 图状态模型 ==========
class GraphState(BaseModel):
    """
    图状态模型（核心状态容器）
    
    这是 LangGraph 中所有节点之间共享的状态对象。
    每个节点都可以读取或修改状态的不同字段。
    
    状态流转流程：
    1. ParseSymptom -> entities（提取症状实体）
    2. RetrieveDocs -> retrieved_docs（检索相关文档）
    3. ReasonReflect -> reflection（推理和反思）
    4. VoteConfidence -> vote_result（聚合多个推理结果）
    5. FallbackRoute -> final_output（生成最终分诊建议）
    """
    patient_input: Dict[str, Any]                    # 患者输入数据（初始输入）
    entities: Optional[List[Dict[str, Any]]] = None  # 从文本中提取的症状实体（ParseSymptom 节点填充）
    retrieved_docs: Optional[List[RetrievedDoc]] = None  # 检索到的医疗文档（RetrieveDocs 节点填充）
    reflection: Optional[Dict[str, Any]] = None      # 推理反思结果（ReasonReflect 节点填充）
    voting_result: Optional[Dict[str, Any]] = None   # 投票聚合结果（VoteConfidence 节点填充）
    routing: Optional[Dict[str, Any]] = None         # 路由决策信息（FallbackRoute 节点填充）
    reasoning_runs: Optional[List[Dict[str, Any]]] = None  # 多次推理运行的结果列表
    final_output: Optional[Dict[str, Any]] = None     # 最终分诊输出（FallbackRoute 节点填充）
    vote_result: Optional[Dict[str, Any]] = None     # 投票结果（VoteConfidence 节点填充，可能与 voting_result 重复）

    # ========== v2.0 新增字段 ==========
    # ESI 分级相关
    esi_assessment: Optional[Dict[str, Any]] = None  # ESI 评估结果 (esi_engine 填充)
    esi_level: Optional[int] = None                  # ESI 等级 (1-5)
    red_flags: Optional[List[str]] = None            # 检测到的危险信号

    # 图推理相关
    graph_context: Optional[Dict[str, Any]] = None   # Neo4j 图上下文 (graph_service 填充)
    risk_associations: Optional[List[Dict]] = None   # 风险关联

    # 动态追问相关
    needs_clarification: bool = False                # 是否需要追问
    clarification_questions: Optional[List[str]] = None  # 待提问的问题
    clarification_response: Optional[str] = None     # 患者的回答
    clarification_count: int = 0                     # 已追问轮数

    # 生命体征 (可选输入)
    vitals: Optional[Dict[str, Any]] = None          # 生命体征数据
    
