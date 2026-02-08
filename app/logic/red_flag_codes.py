"""
Red Flag SNOMED CT Codes Database
=================================

基于公开临床指南的危险信号代码库，用于ESI分诊引擎。

数据来源:
- Canadian CT Head Rule (TBI)
- HEART Score / TIMI Risk (ACS/AMI)
- Wells Criteria / PERC Rule (PE)
- Stanford Classification (Aortic Dissection)
- FAST / NIH Stroke Scale (Stroke)
- ESI Handbook v4 (AHRQ)

注意: SNOMED CT codes 来自公开SNOMED CT Browser
https://browser.ihtsdotools.org/
"""

from typing import Dict, Set, List, Optional
from dataclasses import dataclass
from enum import Enum


class RiskLevel(Enum):
    """风险等级"""
    CRITICAL = 1      # ESI 1 - 立即抢救
    HIGH = 2          # ESI 2 - 高危紧急
    MODERATE = 3      # ESI 3 - 需要评估
    CONDITIONAL = 4   # 需要结合严重程度/上下文判断


@dataclass
class RedFlagCode:
    """Red Flag 代码定义"""
    sctid: str
    name: str
    name_zh: str
    risk_level: RiskLevel
    category: str           # TBI, ACS, PE, STROKE, AORTIC, GENERAL
    guideline_source: str   # 来源指南
    action: str             # 建议动作
    requires_context: bool = False  # 是否需要上下文判断


# =============================================================================
# ESI LEVEL 1: 立即威胁生命 (Immediate Life Threat)
# =============================================================================

LEVEL_1_CRITICAL: Dict[str, RedFlagCode] = {
    # 心肺骤停
    "410429000": RedFlagCode(
        sctid="410429000",
        name="Cardiac arrest",
        name_zh="心脏骤停",
        risk_level=RiskLevel.CRITICAL,
        category="CARDIAC",
        guideline_source="ESI v4",
        action="立即CPR + 除颤"
    ),
    "50574007": RedFlagCode(
        sctid="50574007",
        name="Respiratory arrest",
        name_zh="呼吸骤停",
        risk_level=RiskLevel.CRITICAL,
        category="RESPIRATORY",
        guideline_source="ESI v4",
        action="立即气道管理 + 人工通气"
    ),

    # 休克
    "89138009": RedFlagCode(
        sctid="89138009",
        name="Cardiogenic shock",
        name_zh="心源性休克",
        risk_level=RiskLevel.CRITICAL,
        category="CARDIAC",
        guideline_source="ESI v4",
        action="血管活性药物 + 紧急心脏评估"
    ),
    "27942005": RedFlagCode(
        sctid="27942005",
        name="Hypovolemic shock",
        name_zh="低血容量性休克",
        risk_level=RiskLevel.CRITICAL,
        category="GENERAL",
        guideline_source="ESI v4",
        action="大量液体复苏 + 止血"
    ),
    "76571007": RedFlagCode(
        sctid="76571007",
        name="Septic shock",
        name_zh="感染性休克",
        risk_level=RiskLevel.CRITICAL,
        category="INFECTION",
        guideline_source="Sepsis-3",
        action="1小时Bundle: 血培养+抗生素+液体"
    ),

    # 过敏
    "39579001": RedFlagCode(
        sctid="39579001",
        name="Anaphylaxis",
        name_zh="过敏性休克",
        risk_level=RiskLevel.CRITICAL,
        category="ALLERGY",
        guideline_source="ESI v4",
        action="肾上腺素0.3-0.5mg IM"
    ),

    # 严重心律失常
    "71908006": RedFlagCode(
        sctid="71908006",
        name="Ventricular fibrillation",
        name_zh="心室颤动",
        risk_level=RiskLevel.CRITICAL,
        category="CARDIAC",
        guideline_source="ACLS",
        action="立即除颤"
    ),
    "25569003": RedFlagCode(
        sctid="25569003",
        name="Ventricular tachycardia",
        name_zh="室性心动过速",
        risk_level=RiskLevel.CRITICAL,
        category="CARDIAC",
        guideline_source="ACLS",
        action="评估血流动力学,考虑电复律"
    ),

    # 严重创伤
    "233821000": RedFlagCode(
        sctid="233821000",
        name="Tension pneumothorax",
        name_zh="张力性气胸",
        risk_level=RiskLevel.CRITICAL,
        category="TRAUMA",
        guideline_source="ATLS",
        action="立即胸腔穿刺减压"
    ),
    "410430005": RedFlagCode(
        sctid="410430005",
        name="Massive hemorrhage",
        name_zh="大出血",
        risk_level=RiskLevel.CRITICAL,
        category="TRAUMA",
        guideline_source="ATLS",
        action="压迫止血+大量输血"
    ),

    # 严重意识障碍
    "419045004": RedFlagCode(
        sctid="419045004",
        name="Loss of consciousness",
        name_zh="意识丧失",
        risk_level=RiskLevel.CRITICAL,
        category="NEUROLOGICAL",
        guideline_source="ESI v4",
        action="气道保护+神经评估"
    ),
    "40917007": RedFlagCode(
        sctid="40917007",
        name="Coma",
        name_zh="昏迷",
        risk_level=RiskLevel.CRITICAL,
        category="NEUROLOGICAL",
        guideline_source="ESI v4",
        action="GCS评估+CT"
    ),
}


# =============================================================================
# TBI (Traumatic Brain Injury) - Canadian CT Head Rule
# =============================================================================

TBI_RED_FLAGS: Dict[str, RedFlagCode] = {
    # High Risk (需立即CT)
    "127295002": RedFlagCode(
        sctid="127295002",
        name="Traumatic brain injury",
        name_zh="创伤性脑损伤",
        risk_level=RiskLevel.HIGH,
        category="TBI",
        guideline_source="Canadian CT Head Rule",
        action="CT头颅"
    ),
    "417746004": RedFlagCode(
        sctid="417746004",
        name="Traumatic subdural hemorrhage",
        name_zh="创伤性硬膜下血肿",
        risk_level=RiskLevel.HIGH,
        category="TBI",
        guideline_source="Canadian CT Head Rule",
        action="紧急神经外科会诊"
    ),
    "95453001": RedFlagCode(
        sctid="95453001",
        name="Traumatic epidural hemorrhage",
        name_zh="创伤性硬膜外血肿",
        risk_level=RiskLevel.HIGH,
        category="TBI",
        guideline_source="Canadian CT Head Rule",
        action="紧急神经外科会诊"
    ),
    "110030002": RedFlagCode(
        sctid="110030002",
        name="Concussion",
        name_zh="脑震荡",
        risk_level=RiskLevel.MODERATE,
        category="TBI",
        guideline_source="Canadian CT Head Rule",
        action="神经观察+评估CT指征"
    ),

    # Canadian CT Head Rule 症状
    "422587007": RedFlagCode(
        sctid="422587007",
        name="Nausea and vomiting",
        name_zh="恶心呕吐",
        risk_level=RiskLevel.CONDITIONAL,
        category="TBI",
        guideline_source="Canadian CT Head Rule",
        action="头外伤后呕吐>=2次需CT",
        requires_context=True
    ),
    "386807006": RedFlagCode(
        sctid="386807006",
        name="Memory impairment",
        name_zh="记忆障碍",
        risk_level=RiskLevel.CONDITIONAL,
        category="TBI",
        guideline_source="Canadian CT Head Rule",
        action="逆行性遗忘>30分钟需CT",
        requires_context=True
    ),
    "230690007": RedFlagCode(
        sctid="230690007",
        name="Altered consciousness",
        name_zh="意识改变",
        risk_level=RiskLevel.HIGH,
        category="TBI",
        guideline_source="Canadian CT Head Rule",
        action="GCS<15持续2小时需CT"
    ),

    # 颅骨骨折征象
    "371100002": RedFlagCode(
        sctid="371100002",
        name="Skull fracture",
        name_zh="颅骨骨折",
        risk_level=RiskLevel.HIGH,
        category="TBI",
        guideline_source="Canadian CT Head Rule",
        action="CT确认+神经外科"
    ),
    "110266004": RedFlagCode(
        sctid="110266004",
        name="Basal skull fracture",
        name_zh="颅底骨折",
        risk_level=RiskLevel.HIGH,
        category="TBI",
        guideline_source="Canadian CT Head Rule",
        action="CT确认+监测脑脊液漏"
    ),

    # 高危机制
    "242603007": RedFlagCode(
        sctid="242603007",
        name="Fall from height",
        name_zh="高处坠落",
        risk_level=RiskLevel.CONDITIONAL,
        category="TBI",
        guideline_source="Canadian CT Head Rule",
        action=">3英尺或>5级台阶需CT",
        requires_context=True
    ),
    "418399005": RedFlagCode(
        sctid="418399005",
        name="Motor vehicle accident",
        name_zh="机动车事故",
        risk_level=RiskLevel.CONDITIONAL,
        category="TBI",
        guideline_source="Canadian CT Head Rule",
        action="评估受伤机制严重程度",
        requires_context=True
    ),
}


# =============================================================================
# ACS/AMI (Acute Coronary Syndrome) - HEART Score
# =============================================================================

CARDIAC_RED_FLAGS: Dict[str, RedFlagCode] = {
    # 心梗
    "22298006": RedFlagCode(
        sctid="22298006",
        name="Myocardial infarction",
        name_zh="心肌梗死",
        risk_level=RiskLevel.CRITICAL,
        category="ACS",
        guideline_source="AHA/ACC STEMI Guidelines",
        action="ECG+肌钙蛋白+紧急PCI评估"
    ),
    "401303003": RedFlagCode(
        sctid="401303003",
        name="Acute ST elevation myocardial infarction",
        name_zh="急性ST段抬高型心梗",
        risk_level=RiskLevel.CRITICAL,
        category="ACS",
        guideline_source="AHA/ACC STEMI Guidelines",
        action="Door-to-balloon <90分钟"
    ),
    "401314000": RedFlagCode(
        sctid="401314000",
        name="Non-ST elevation myocardial infarction",
        name_zh="非ST段抬高型心梗",
        risk_level=RiskLevel.HIGH,
        category="ACS",
        guideline_source="AHA/ACC NSTEMI Guidelines",
        action="风险分层+抗栓+早期介入"
    ),

    # 胸痛
    "29857009": RedFlagCode(
        sctid="29857009",
        name="Chest pain",
        name_zh="胸痛",
        risk_level=RiskLevel.CONDITIONAL,
        category="ACS",
        guideline_source="HEART Score",
        action="ECG+肌钙蛋白, 严重时ESI 2",
        requires_context=True
    ),
    "426396005": RedFlagCode(
        sctid="426396005",
        name="Cardiac chest pain",
        name_zh="心源性胸痛",
        risk_level=RiskLevel.HIGH,
        category="ACS",
        guideline_source="HEART Score",
        action="ECG+肌钙蛋白+心内科会诊"
    ),

    # 放射痛
    "102588006": RedFlagCode(
        sctid="102588006",
        name="Pain radiating to arm",
        name_zh="放射至手臂的疼痛",
        risk_level=RiskLevel.HIGH,
        category="ACS",
        guideline_source="HEART Score",
        action="高度怀疑ACS"
    ),
    "102589003": RedFlagCode(
        sctid="102589003",
        name="Pain radiating to jaw",
        name_zh="放射至下颌的疼痛",
        risk_level=RiskLevel.HIGH,
        category="ACS",
        guideline_source="HEART Score",
        action="高度怀疑ACS"
    ),

    # 伴随症状
    "415690000": RedFlagCode(
        sctid="415690000",
        name="Diaphoresis",
        name_zh="大汗淋漓",
        risk_level=RiskLevel.CONDITIONAL,
        category="ACS",
        guideline_source="HEART Score",
        action="胸痛+大汗高度怀疑ACS",
        requires_context=True
    ),

    # 不稳定心绞痛
    "25106000": RedFlagCode(
        sctid="25106000",
        name="Unstable angina",
        name_zh="不稳定型心绞痛",
        risk_level=RiskLevel.HIGH,
        category="ACS",
        guideline_source="AHA/ACC",
        action="抗栓+入院观察"
    ),

    # 心衰
    "84114007": RedFlagCode(
        sctid="84114007",
        name="Heart failure",
        name_zh="心力衰竭",
        risk_level=RiskLevel.HIGH,
        category="CARDIAC",
        guideline_source="ESC Heart Failure",
        action="利尿+评估诱因"
    ),
    "67362008": RedFlagCode(
        sctid="67362008",
        name="Acute heart failure",
        name_zh="急性心力衰竭",
        risk_level=RiskLevel.HIGH,
        category="CARDIAC",
        guideline_source="ESC Heart Failure",
        action="利尿+无创通气+评估原因"
    ),

    # 心律失常
    "49436004": RedFlagCode(
        sctid="49436004",
        name="Atrial fibrillation",
        name_zh="房颤",
        risk_level=RiskLevel.MODERATE,
        category="CARDIAC",
        guideline_source="ESC AF Guidelines",
        action="心率控制+抗凝评估"
    ),
    "233917008": RedFlagCode(
        sctid="233917008",
        name="Atrial fibrillation with rapid ventricular response",
        name_zh="快速房颤",
        risk_level=RiskLevel.HIGH,
        category="CARDIAC",
        guideline_source="ESC AF Guidelines",
        action="紧急心率控制"
    ),
}


# =============================================================================
# PE (Pulmonary Embolism) - Wells Criteria
# =============================================================================

PE_RED_FLAGS: Dict[str, RedFlagCode] = {
    # PE确诊
    "59282003": RedFlagCode(
        sctid="59282003",
        name="Pulmonary embolism",
        name_zh="肺栓塞",
        risk_level=RiskLevel.HIGH,
        category="PE",
        guideline_source="ESC PE Guidelines",
        action="抗凝+评估溶栓指征"
    ),
    "706870000": RedFlagCode(
        sctid="706870000",
        name="Acute pulmonary embolism",
        name_zh="急性肺栓塞",
        risk_level=RiskLevel.HIGH,
        category="PE",
        guideline_source="ESC PE Guidelines",
        action="CTPA确诊+抗凝"
    ),
    "233935004": RedFlagCode(
        sctid="233935004",
        name="Massive pulmonary embolism",
        name_zh="大面积肺栓塞",
        risk_level=RiskLevel.CRITICAL,
        category="PE",
        guideline_source="ESC PE Guidelines",
        action="考虑溶栓/取栓"
    ),

    # Wells Criteria 症状
    "267036007": RedFlagCode(
        sctid="267036007",
        name="Dyspnea",
        name_zh="呼吸困难",
        risk_level=RiskLevel.CONDITIONAL,
        category="PE",
        guideline_source="Wells Criteria",
        action="结合其他因素评估PE可能性",
        requires_context=True
    ),
    "89138009": RedFlagCode(
        sctid="89138009",
        name="Pleuritic chest pain",
        name_zh="胸膜性胸痛",
        risk_level=RiskLevel.CONDITIONAL,
        category="PE",
        guideline_source="Wells Criteria",
        action="吸气加重的胸痛考虑PE",
        requires_context=True
    ),
    "66857006": RedFlagCode(
        sctid="66857006",
        name="Hemoptysis",
        name_zh="咯血",
        risk_level=RiskLevel.HIGH,
        category="PE",
        guideline_source="Wells Criteria",
        action="Wells +1, 评估出血原因"
    ),

    # DVT相关
    "128053003": RedFlagCode(
        sctid="128053003",
        name="Deep vein thrombosis",
        name_zh="深静脉血栓",
        risk_level=RiskLevel.HIGH,
        category="PE",
        guideline_source="Wells Criteria",
        action="抗凝+评估PE"
    ),
    "95573000": RedFlagCode(
        sctid="95573000",
        name="Leg swelling",
        name_zh="下肢肿胀",
        risk_level=RiskLevel.CONDITIONAL,
        category="PE",
        guideline_source="Wells Criteria",
        action="单侧下肢肿胀评估DVT",
        requires_context=True
    ),

    # 高危因素
    "271594007": RedFlagCode(
        sctid="271594007",
        name="Syncope",
        name_zh="晕厥",
        risk_level=RiskLevel.HIGH,
        category="PE",
        guideline_source="ESC PE Guidelines",
        action="PE伴晕厥提示高危"
    ),
    "195080001": RedFlagCode(
        sctid="195080001",
        name="Tachycardia",
        name_zh="心动过速",
        risk_level=RiskLevel.CONDITIONAL,
        category="PE",
        guideline_source="Wells Criteria",
        action="HR>100 Wells +1.5",
        requires_context=True
    ),
}


# =============================================================================
# Aortic Dissection - Stanford Classification
# =============================================================================

AORTIC_RED_FLAGS: Dict[str, RedFlagCode] = {
    # 主动脉夹层
    "308546005": RedFlagCode(
        sctid="308546005",
        name="Aortic dissection",
        name_zh="主动脉夹层",
        risk_level=RiskLevel.CRITICAL,
        category="AORTIC",
        guideline_source="ESC Aortic Diseases",
        action="紧急CTA+控制血压心率"
    ),
    "59282003": RedFlagCode(
        sctid="59282003",
        name="Type A aortic dissection",
        name_zh="A型主动脉夹层",
        risk_level=RiskLevel.CRITICAL,
        category="AORTIC",
        guideline_source="Stanford Classification",
        action="紧急外科手术"
    ),
    "253682005": RedFlagCode(
        sctid="253682005",
        name="Type B aortic dissection",
        name_zh="B型主动脉夹层",
        risk_level=RiskLevel.HIGH,
        category="AORTIC",
        guideline_source="Stanford Classification",
        action="控制血压+监测"
    ),

    # 特征性疼痛
    "426206001": RedFlagCode(
        sctid="426206001",
        name="Tearing chest pain",
        name_zh="撕裂样胸痛",
        risk_level=RiskLevel.HIGH,
        category="AORTIC",
        guideline_source="ESC Aortic Diseases",
        action="CTA排除夹层"
    ),
    "161891005": RedFlagCode(
        sctid="161891005",
        name="Back pain",
        name_zh="背痛",
        risk_level=RiskLevel.CONDITIONAL,
        category="AORTIC",
        guideline_source="ESC Aortic Diseases",
        action="胸痛+背痛考虑夹层",
        requires_context=True
    ),

    # 相关征象
    "13213009": RedFlagCode(
        sctid="13213009",
        name="Blood pressure difference between arms",
        name_zh="双臂血压差",
        risk_level=RiskLevel.HIGH,
        category="AORTIC",
        guideline_source="ESC Aortic Diseases",
        action="差值>20mmHg提示夹层"
    ),
    "64572001": RedFlagCode(
        sctid="64572001",
        name="Hypertension",
        name_zh="高血压",
        risk_level=RiskLevel.CONDITIONAL,
        category="AORTIC",
        guideline_source="ESC Aortic Diseases",
        action="夹层高危因素",
        requires_context=True
    ),
}


# =============================================================================
# Stroke - FAST Criteria
# =============================================================================

STROKE_RED_FLAGS: Dict[str, RedFlagCode] = {
    # 卒中
    "230690007": RedFlagCode(
        sctid="230690007",
        name="Stroke",
        name_zh="卒中",
        risk_level=RiskLevel.CRITICAL,
        category="STROKE",
        guideline_source="AHA Stroke Guidelines",
        action="CT排除出血+评估溶栓"
    ),
    "422504002": RedFlagCode(
        sctid="422504002",
        name="Ischemic stroke",
        name_zh="缺血性卒中",
        risk_level=RiskLevel.CRITICAL,
        category="STROKE",
        guideline_source="AHA Stroke Guidelines",
        action="4.5h内评估溶栓"
    ),
    "274100004": RedFlagCode(
        sctid="274100004",
        name="Hemorrhagic stroke",
        name_zh="出血性卒中",
        risk_level=RiskLevel.CRITICAL,
        category="STROKE",
        guideline_source="AHA Stroke Guidelines",
        action="控制血压+神经外科会诊"
    ),
    "266257000": RedFlagCode(
        sctid="266257000",
        name="Transient ischemic attack",
        name_zh="短暂性脑缺血发作",
        risk_level=RiskLevel.HIGH,
        category="STROKE",
        guideline_source="AHA TIA Guidelines",
        action="MRI+颈动脉评估+抗栓"
    ),

    # FAST症状
    "398979000": RedFlagCode(
        sctid="398979000",
        name="Facial weakness",
        name_zh="面部无力",
        risk_level=RiskLevel.HIGH,
        category="STROKE",
        guideline_source="FAST",
        action="单侧面瘫激活卒中绿道"
    ),
    "249966004": RedFlagCode(
        sctid="249966004",
        name="Arm weakness",
        name_zh="上肢无力",
        risk_level=RiskLevel.HIGH,
        category="STROKE",
        guideline_source="FAST",
        action="单侧肢体无力激活卒中绿道"
    ),
    "29164008": RedFlagCode(
        sctid="29164008",
        name="Speech disturbance",
        name_zh="言语障碍",
        risk_level=RiskLevel.HIGH,
        category="STROKE",
        guideline_source="FAST",
        action="言语含糊激活卒中绿道"
    ),
    "289530006": RedFlagCode(
        sctid="289530006",
        name="Dysarthria",
        name_zh="构音障碍",
        risk_level=RiskLevel.HIGH,
        category="STROKE",
        guideline_source="FAST",
        action="激活卒中绿道"
    ),

    # 其他卒中症状
    "246636008": RedFlagCode(
        sctid="246636008",
        name="Hemiparesis",
        name_zh="偏瘫",
        risk_level=RiskLevel.HIGH,
        category="STROKE",
        guideline_source="NIH Stroke Scale",
        action="激活卒中绿道"
    ),
    "422400008": RedFlagCode(
        sctid="422400008",
        name="Visual field defect",
        name_zh="视野缺损",
        risk_level=RiskLevel.HIGH,
        category="STROKE",
        guideline_source="NIH Stroke Scale",
        action="评估卒中"
    ),
    "25064002": RedFlagCode(
        sctid="25064002",
        name="Severe sudden headache",
        name_zh="突发剧烈头痛",
        risk_level=RiskLevel.HIGH,
        category="STROKE",
        guideline_source="SAH Guidelines",
        action="CT+腰穿排除SAH"
    ),
}


# =============================================================================
# 其他高危情况
# =============================================================================

GENERAL_RED_FLAGS: Dict[str, RedFlagCode] = {
    # 感染
    "91302008": RedFlagCode(
        sctid="91302008",
        name="Sepsis",
        name_zh="脓毒症",
        risk_level=RiskLevel.HIGH,
        category="INFECTION",
        guideline_source="Sepsis-3",
        action="1小时Bundle"
    ),
    "10509002": RedFlagCode(
        sctid="10509002",
        name="Meningitis",
        name_zh="脑膜炎",
        risk_level=RiskLevel.HIGH,
        category="INFECTION",
        guideline_source="IDSA Meningitis",
        action="血培养+经验性抗生素+腰穿"
    ),

    # 中毒
    "75478009": RedFlagCode(
        sctid="75478009",
        name="Poisoning",
        name_zh="中毒",
        risk_level=RiskLevel.HIGH,
        category="TOXICOLOGY",
        guideline_source="Toxicology Guidelines",
        action="洗胃/拮抗剂+对症"
    ),
    "212416003": RedFlagCode(
        sctid="212416003",
        name="Drug overdose",
        name_zh="药物过量",
        risk_level=RiskLevel.HIGH,
        category="TOXICOLOGY",
        guideline_source="Toxicology Guidelines",
        action="解毒剂+支持治疗"
    ),

    # 精神科急症
    "371631005": RedFlagCode(
        sctid="371631005",
        name="Suicidal ideation",
        name_zh="自杀观念",
        risk_level=RiskLevel.HIGH,
        category="PSYCHIATRIC",
        guideline_source="Psychiatric Emergency",
        action="1:1看护+精神科会诊"
    ),
    "224960003": RedFlagCode(
        sctid="224960003",
        name="Self-harm",
        name_zh="自伤",
        risk_level=RiskLevel.HIGH,
        category="PSYCHIATRIC",
        guideline_source="Psychiatric Emergency",
        action="创伤处理+精神科评估"
    ),

    # 急腹症
    "74400008": RedFlagCode(
        sctid="74400008",
        name="Appendicitis",
        name_zh="阑尾炎",
        risk_level=RiskLevel.MODERATE,
        category="ABDOMINAL",
        guideline_source="Surgical Guidelines",
        action="CT确诊+外科会诊"
    ),
    "48340000": RedFlagCode(
        sctid="48340000",
        name="Acute cholecystitis",
        name_zh="急性胆囊炎",
        risk_level=RiskLevel.MODERATE,
        category="ABDOMINAL",
        guideline_source="Tokyo Guidelines",
        action="超声+抗生素+外科"
    ),
    "3419005": RedFlagCode(
        sctid="3419005",
        name="Ruptured abdominal aortic aneurysm",
        name_zh="腹主动脉瘤破裂",
        risk_level=RiskLevel.CRITICAL,
        category="VASCULAR",
        guideline_source="ESVS AAA Guidelines",
        action="紧急CTA+外科手术"
    ),

    # 产科急症
    "17860005": RedFlagCode(
        sctid="17860005",
        name="Ectopic pregnancy",
        name_zh="宫外孕",
        risk_level=RiskLevel.HIGH,
        category="OBSTETRIC",
        guideline_source="ACOG Guidelines",
        action="超声+β-hCG+外科评估"
    ),
}


# =============================================================================
# 合并所有codes
# =============================================================================

ALL_RED_FLAG_CODES: Dict[str, RedFlagCode] = {
    **LEVEL_1_CRITICAL,
    **TBI_RED_FLAGS,
    **CARDIAC_RED_FLAGS,
    **PE_RED_FLAGS,
    **AORTIC_RED_FLAGS,
    **STROKE_RED_FLAGS,
    **GENERAL_RED_FLAGS,
}

# 按ESI Level分组的SCTID集合
LEVEL_1_SCTIDS: Set[str] = {
    code.sctid for code in ALL_RED_FLAG_CODES.values()
    if code.risk_level == RiskLevel.CRITICAL
}

LEVEL_2_SCTIDS: Set[str] = {
    code.sctid for code in ALL_RED_FLAG_CODES.values()
    if code.risk_level == RiskLevel.HIGH
}

CONDITIONAL_SCTIDS: Set[str] = {
    code.sctid for code in ALL_RED_FLAG_CODES.values()
    if code.risk_level == RiskLevel.CONDITIONAL
}

# 按疾病类别分组
CODES_BY_CATEGORY: Dict[str, Set[str]] = {}
for code in ALL_RED_FLAG_CODES.values():
    if code.category not in CODES_BY_CATEGORY:
        CODES_BY_CATEGORY[code.category] = set()
    CODES_BY_CATEGORY[code.category].add(code.sctid)


# =============================================================================
# 辅助函数
# =============================================================================

def get_red_flag_info(sctid: str) -> Optional[RedFlagCode]:
    """获取Red Flag代码的详细信息"""
    return ALL_RED_FLAG_CODES.get(sctid)


def check_red_flags(sctids: List[str]) -> List[RedFlagCode]:
    """检查一组SNOMED codes中的Red Flags"""
    flags = []
    for sctid in sctids:
        if sctid in ALL_RED_FLAG_CODES:
            flags.append(ALL_RED_FLAG_CODES[sctid])
    return flags


def get_highest_risk_level(sctids: List[str]) -> Optional[RiskLevel]:
    """获取一组codes中最高的风险等级"""
    levels = []
    for sctid in sctids:
        if sctid in ALL_RED_FLAG_CODES:
            levels.append(ALL_RED_FLAG_CODES[sctid].risk_level)
    if levels:
        return min(levels, key=lambda x: x.value)  # CRITICAL=1 is highest
    return None


def get_codes_by_category(category: str) -> List[RedFlagCode]:
    """获取特定类别的所有codes"""
    return [
        code for code in ALL_RED_FLAG_CODES.values()
        if code.category == category
    ]


# =============================================================================
# 统计信息
# =============================================================================

def get_stats() -> Dict[str, int]:
    """获取Red Flag代码库统计"""
    return {
        "total_codes": len(ALL_RED_FLAG_CODES),
        "level_1_critical": len(LEVEL_1_SCTIDS),
        "level_2_high": len(LEVEL_2_SCTIDS),
        "conditional": len(CONDITIONAL_SCTIDS),
        "categories": len(CODES_BY_CATEGORY),
        "tbi_codes": len(TBI_RED_FLAGS),
        "cardiac_codes": len(CARDIAC_RED_FLAGS),
        "pe_codes": len(PE_RED_FLAGS),
        "stroke_codes": len(STROKE_RED_FLAGS),
        "aortic_codes": len(AORTIC_RED_FLAGS),
    }


if __name__ == "__main__":
    stats = get_stats()
    print("=" * 50)
    print("Red Flag Codes Database Statistics")
    print("=" * 50)
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 50)
    print("Categories:")
    print("=" * 50)
    for cat, codes in CODES_BY_CATEGORY.items():
        print(f"  {cat}: {len(codes)} codes")
