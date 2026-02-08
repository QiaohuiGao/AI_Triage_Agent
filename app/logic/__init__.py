"""
Logic Module
============
临床逻辑引擎模块

包含：
- ESI Engine: 五级分诊逻辑
- Graph Service: Neo4j 知识图谱推理服务
"""

from .esi_engine import (
    ESIEngine,
    ESILevel,
    ESIAssessment,
    calculate_esi,
    is_high_risk
)

from .graph_service import (
    GraphService,
    GraphContext,
    get_graph_service,
    enrich_with_graph,
    find_risks
)

__all__ = [
    # ESI Engine
    "ESIEngine",
    "ESILevel",
    "ESIAssessment",
    "calculate_esi",
    "is_high_risk",
    # Graph Service
    "GraphService",
    "GraphContext",
    "get_graph_service",
    "enrich_with_graph",
    "find_risks",
]
