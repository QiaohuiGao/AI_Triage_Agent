from typing import List
from .schemas import RetrievalDoc
from .embed_store import VectorStore
from .config import CFG

SYMPTOM_DB, CONDITION_DB, CAREPATH_DB = VectorStore(), VectorStore(), VectorStore()
SYMPTOM_DB.add([{"id":"sym1","text":"Chest pain may be from angina or muscle strain.","meta":{"level":"symptom"}},
                {"id":"sym2","text":"Rash indicates allergic dermatitis or viral infection.","meta":{"level":"symptom"}}])
CONDITION_DB.add([{"id":"cond1","text":"Angina pectoris is exertional chest discomfort relieved by rest.","meta":{"level":"condition"}},
                  {"id":"cond2","text":"Allergic dermatitis is an itchy rash from contact allergens.","meta":{"level":"condition"}}])
CAREPATH_DB.add([{"id":"path1","text":"Cardiology handles chest pain and heart disease.","meta":{"level":"carepath"}},
                 {"id":"path2","text":"Dermatology treats skin rashes and lesions.","meta":{"level":"carepath"}}])

def retrieve_context(query:str)->List[RetrievalDoc]:
    sym=SYMPTOM_DB.search(query,CFG.vector.top_k)
    con=CONDITION_DB.search(query,CFG.vector.top_k)
    pat=CAREPATH_DB.search(query,CFG.vector.top_k)
    merged=[]
    for docs,w in [(sym,CFG.vector.w_symptom),(con,CFG.vector.w_condition),(pat,CFG.vector.w_carepath)]:
        for d in docs:
            merged.append(RetrievalDoc(id=d.id,text=d.text,score=d.score*w,meta=d.meta))
    merged.sort(key=lambda x:-x.score)
    return merged[:CFG.vector.top_k*2]