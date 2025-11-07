"""
投票置信度节点 (vote_confidence.py)
==================================
本节点负责聚合多次推理结果，计算平均置信度和一致性稳定性。

功能：
- 聚合多次推理运行（reasoning_runs）的结果
- 计算平均置信度（avg_confidence）
- 计算一致性（agreement）：多个推理结果的一致性
- 计算稳定性（stability）：置信度分布的稳定性

这个节点实现了"投票机制"，通过多次推理来提高结果的可靠性。
如果多次推理的结果一致，则置信度更高。

输入：GraphState.reasoning_runs
输出：GraphState.vote_result
"""

from typing import List, Dict, Any
from app.schemas import GraphState

def vote_confidence(state: dict) -> dict:
    """
    投票置信度节点
    
    聚合多次推理运行的结果，计算：
    - 平均置信度：所有推理结果的置信度平均值
    - 一致性：多个推理结果的一致性（1 - 条件多样性比例）
    - 稳定性：置信度分布的稳定性（基于置信度范围）
    
    参数:
        state: GraphState 对象，包含 reasoning_runs 字段
    
    返回:
        更新后的 GraphState，包含 vote_result 字段
    """
    # ========== 获取推理运行结果 ==========
    # 从 GraphState 中获取多次推理运行的结果列表
    # 如果为空，返回默认值
    runs: List[Dict[str, Any]] = getattr(state, "reasoning_runs", []) or []
    
    if not runs:
        # 如果没有推理运行结果，返回默认值
        state.vote_result = {
            "avg_confidence": 0,    # 平均置信度为 0
            "agreement": 0,         # 一致性为 0
            "stability": 1.0        # 稳定性为 1.0（最高）
        }
        return state

    # ========== 计算平均置信度 ==========
    # 提取所有推理运行的置信度，计算平均值
    confidences = [r.get("confidence", 0) for r in runs]
    avg = sum(confidences) / len(confidences)
    
    #我感觉这个基本都涉及不到什么推理了，就是进行匹配就足够了，只有疾病诊断之后，给出科室建议，或者问询二次问题的时候需要一定的内容生成

    # ========== 计算一致性 ==========
    # 一致性 = 1 - 条件多样性比例
    # 如果所有推理结果的条件都相同，则一致性为 1
    # 如果条件完全不同，则一致性为 0
    agreement = len(set(r.get("condition") for r in runs)) / len(runs)

    # ========== 计算稳定性 ==========
    # 稳定性基于置信度的分布范围
    # 置信度范围越小，稳定性越高
    # 使用 max(0.0001, ...) 避免除零错误
    st = max(0.0001, (max(confidences) - min(confidences)))

    # ========== 更新状态 ==========
    # 将投票结果添加到 GraphState 中
    # 后续节点（FallbackRoute）会使用这些信息进行路由决策
    state.vote_result = {
        "avg_confidence": round(avg, 2),           # 平均置信度（保留2位小数）
        "agreement": round(1.0 - agreement, 2),     # 一致性（1 - 多样性比例）
        "stability": round(1.0 / (1.0 + st), 2)    # 稳定性（基于置信度范围）
    }

    return state
