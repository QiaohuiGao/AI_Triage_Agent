"""
工具函数模块 (utils.py)
=======================
本模块提供医疗编码系统的查找工具函数，用于将症状的自然语言描述
映射到标准化的医疗编码系统。

支持的编码系统：
- SNOMED CT：系统化医学术语集，用于临床术语标准化
- ICD-10：国际疾病分类第10版，用于疾病诊断编码

这些编码可用于：
- 医疗记录的标准化
- 跨系统的数据交换
- 统计分析
- 与电子病历系统集成
"""

# ========== SNOMED CT 编码字典 ==========
# SNOMED CT (Systematized Nomenclature of Medicine -- Clinical Terms)
# 是国际标准的临床术语集，用于编码医疗概念
SNOMED = {
    "chest pain": "29857009",           # 胸痛的 SNOMED 编码
    "shortness of breath": "267036007",  # 呼吸困难的 SNOMED 编码
    "fever": "386661006"                 # 发热的 SNOMED 编码
}

# ========== ICD-10 编码字典 ==========
# ICD-10 (International Classification of Diseases, 10th Revision)
# 是世界卫生组织制定的疾病分类标准，广泛用于疾病诊断编码
ICD10 = {
    "chest pain": "R07.9",           # 胸痛的 ICD-10 编码（未特指的胸痛）
    "shortness of breath": "R06.02", # 呼吸困难的 ICD-10 编码
    "fever": "R50.9"                 # 发热的 ICD-10 编码（未特指的发热）
}

# ========== 编码查找函数 ==========
def snomed_lookup(surface: str):
    """
    根据症状的表面形式查找对应的 SNOMED CT 编码
    
    参数:
        surface: 症状的自然语言描述（如 "chest pain"）
    
    返回:
        SNOMED CT 编码字符串，如果未找到则返回 None
    """
    return SNOMED.get(surface.lower())

def icd_lookup(surface: str):
    """
    根据症状的表面形式查找对应的 ICD-10 编码
    
    参数:
        surface: 症状的自然语言描述（如 "chest pain"）
    
    返回:
        ICD-10 编码字符串，如果未找到则返回 None
    """
    return ICD10.get(surface.lower())
