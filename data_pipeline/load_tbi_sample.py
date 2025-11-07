"""
加载 TBI（创伤性脑损伤）样本数据到数据库

该脚本包含预定义的 TBI 医疗指南记录，并将它们插入到 PostgreSQL 数据库中。
每条记录包含：
- 标题、章节、来源、级别、日期等元数据
- 医疗指南文本内容
- SNOMED CT 编码（医学术语标准编码）
- ICD 编码（疾病分类编码）
- 标签
- 嵌入向量（通过 embedder 生成）

主要功能：
1. 定义 TBI 医疗指南样本数据
2. 为每条记录生成嵌入向量
3. 创建数据库表（如果不存在）
4. 将记录插入数据库
"""

import numpy as np
from datetime import date
from data_pipeline.common_db import pg_conn
from data_pipeline.embedder import embed

# TBI（创伤性脑损伤）医疗指南样本数据
# 包含多个不同来源和主题的医疗指南记录
tbi_records = [
    {
        "title": "TBI Acute Care",
        "section": "Initial Assessment",
        "source": "NICE",
        "level": "high",
        "date": "2023-06-10",
        "url": "https://www.nice.org.uk/guidance/ng155",
        "text": "Patients with suspected traumatic brain injury (TBI) should receive a rapid neurological assessment and GCS scoring immediately upon admission. Early airway stabilization and CT head scan within 1 hour are recommended for those with GCS ≤ 13 or focal neurological deficit.",
        "snomed_ids": ["386661006"],  # Example: Traumatic brain injury
        "icd_codes": ["S06.0"],
        "tags": ["TBI", "acute", "assessment"]
    },
    {
        "title": "TBI Acute Care",
        "section": "Airway and Breathing",
        "source": "NICE",
        "level": "high",
        "date": "2023-06-10",
        "url": "https://www.nice.org.uk/guidance/ng155",
        "text": "Maintain oxygen saturation above 94% using supplemental oxygen. Intubate patients with GCS ≤ 8 or those unable to maintain airway patency. Avoid hyperventilation unless there are signs of raised intracranial pressure.",
        "snomed_ids": ["371048007"],  # Airway management
        "icd_codes": ["S06.2"],
        "tags": ["TBI", "airway", "breathing"]
    },
    {
        "title": "TBI Acute Care",
        "section": "Circulation and Hemodynamics",
        "source": "NICE",
        "level": "medium",
        "date": "2023-06-10",
        "url": "https://www.nice.org.uk/guidance/ng155",
        "text": "Maintain systolic blood pressure ≥ 100 mmHg in adults. Use isotonic fluids and avoid hypotonic solutions to prevent cerebral edema. Monitor heart rate and maintain normothermia.",
        "snomed_ids": ["249366005"],
        "icd_codes": ["I95.9"],
        "tags": ["TBI", "blood pressure", "resuscitation"]
    },
    {
        "title": "TBI Imaging",
        "section": "Neuroimaging Indications",
        "source": "AANS",
        "level": "high",
        "date": "2022-11-14",
        "url": "https://www.aans.org/Guidelines/TBI",
        "text": "Perform non-contrast CT for all moderate-to-severe head injuries or patients on anticoagulants. MRI is recommended for diffuse axonal injury evaluation when CT findings are inconclusive.",
        "snomed_ids": ["168130009"],
        "icd_codes": ["S06.9"],
        "tags": ["TBI", "CT", "MRI", "diagnosis"]
    },
    {
        "title": "TBI Management",
        "section": "Intracranial Pressure Monitoring",
        "source": "AHA",
        "level": "high",
        "date": "2022-09-10",
        "url": "https://www.ahajournals.org/journal/stroke",
        "text": "Initiate ICP monitoring in patients with severe TBI (GCS ≤ 8) and abnormal CT findings. Maintain ICP below 22 mmHg and cerebral perfusion pressure between 60–70 mmHg.",
        "snomed_ids": ["302215000"],
        "icd_codes": ["S06.4"],
        "tags": ["TBI", "ICP", "monitoring"]
    },
    {
        "title": "TBI Management",
        "section": "Surgical Indications",
        "source": "NICE",
        "level": "high",
        "date": "2023-06-10",
        "url": "https://www.nice.org.uk/guidance/ng155",
        "text": "Perform urgent craniotomy for mass lesions causing midline shift or signs of herniation. Evacuate hematoma when volume >30 mL or midline shift >5 mm regardless of GCS.",
        "snomed_ids": ["116293008"],
        "icd_codes": ["S06.5"],
        "tags": ["TBI", "surgery", "hematoma"]
    },
    {
        "title": "TBI Rehabilitation",
        "section": "Early Rehabilitation",
        "source": "WHO",
        "level": "medium",
        "date": "2023-05-22",
        "url": "https://www.who.int/publications/tbi-rehabilitation",
        "text": "Begin early multidisciplinary rehabilitation once the patient is hemodynamically stable. Include physical, cognitive, and psychological interventions to improve long-term outcomes.",
        "snomed_ids": ["22529005"],
        "icd_codes": ["S06.8"],
        "tags": ["TBI", "rehab", "recovery"]
    },
    {
        "title": "TBI Follow-up",
        "section": "Discharge Planning",
        "source": "NICE",
        "level": "medium",
        "date": "2023-06-10",
        "url": "https://www.nice.org.uk/guidance/ng155",
        "text": "Ensure safe discharge with follow-up within 7 days. Provide written information on red flag symptoms such as persistent vomiting, severe headache, or confusion. Encourage gradual return to normal activity.",
        "snomed_ids": ["281647001"],
        "icd_codes": ["S06.7"],
        "tags": ["TBI", "follow-up", "outpatient"]
    },
    {
        "title": "TBI Long-term Outcomes",
        "section": "Neuropsychological Sequelae",
        "source": "CDC",
        "level": "medium",
        "date": "2022-04-30",
        "url": "https://www.cdc.gov/traumaticbraininjury",
        "text": "Monitor cognitive, emotional, and behavioral symptoms up to 6 months after injury. Offer neuropsychological evaluation and targeted interventions when deficits persist.",
        "snomed_ids": ["371048007"],
        "icd_codes": ["F07.2"],
        "tags": ["TBI", "neuro", "cognition"]
    },
    {
        "title": "TBI Pediatric Considerations",
        "section": "Children and Adolescents",
        "source": "AAP",
        "level": "high",
        "date": "2023-01-10",
        "url": "https://pediatrics.aappublications.org",
        "text": "In children with TBI, avoid hypotension and hypoxia aggressively. Use weight-based fluid resuscitation. Repeat imaging only if neurological deterioration occurs.",
        "snomed_ids": ["24857008"],
        "icd_codes": ["S06.0"],
        "tags": ["TBI", "pediatric", "children"]
    }
]

def insert_tbi(records):
    """
    将 TBI 医疗指南记录插入到 PostgreSQL 数据库
    
    参数:
        records: 包含医疗指南记录的列表，每个记录是一个字典
    
    流程:
        1. 创建 medical_guidelines 表（如果不存在）
        2. 遍历每条记录：
           - 使用 embedder 为文本生成嵌入向量
           - 将向量转换为二进制格式（BYTEA）
           - 插入数据库
    """
    with pg_conn() as conn:
        cur = conn.cursor()
        
        # 创建医疗指南表（如果不存在）
        # 表结构说明：
        # - id: 自增主键
        # - title, section, source, level, date: 元数据字段
        # - text: 医疗指南的文本内容
        # - snomed_ids: SNOMED CT 编码数组（医学术语标准编码系统）
        # - icd_codes: ICD 编码数组（国际疾病分类编码）
        # - tags: 标签数组
        # - embedding: 文本的嵌入向量（二进制格式，BYTEA 类型）
        cur.execute("""
        CREATE TABLE IF NOT EXISTS medical_guidelines (
            id SERIAL PRIMARY KEY,
            title TEXT,
            section TEXT,
            source TEXT,
            level TEXT,
            date DATE,
            text TEXT,
            snomed_ids TEXT[],
            icd_codes TEXT[],
            tags TEXT[],
            embedding BYTEA
        );
        """)
        
        # 遍历每条记录，生成嵌入向量并插入数据库
        for r in records:
            # 为文本生成嵌入向量
            # embed() 返回一个 numpy 数组，[0] 取第一个（也是唯一的）向量
            vec = embed([r["text"]])[0]
            
            # 插入记录到数据库
            # vec.tobytes(): 将 numpy 数组转换为二进制格式，以便存储到 BYTEA 字段
            cur.execute("""
            INSERT INTO medical_guidelines (title, section, source, level, date, text, snomed_ids, icd_codes, tags, embedding)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (r["title"], r["section"], r["source"], r["level"], r["date"], r["text"],
                  r["snomed_ids"], r["icd_codes"], r["tags"], vec.tobytes()))
    
    print(f"Inserted {len(records)} TBI guideline records")

if __name__ == "__main__":
    insert_tbi(tbi_records)