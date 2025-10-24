from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class VectorCfg:
    dim: int = 1024
    top_k: int = 5
    min_hits: int = 2
    w_symptom: float = 0.4
    w_condition: float = 0.4
    w_carepath: float = 0.2

@dataclass(frozen=True)
class Thresholds:
    low_conf: float = 0.55
    high_conf: float = 0.78
    min_agreement: float = 0.55

@dataclass(frozen=True)
class LLMCfg:
    ensemble_runs: int = 3

@dataclass(frozen=True)
class AppCfg:
    vector = VectorCfg()
    th = Thresholds()
    llm = LLMCfg()

CFG = AppCfg()