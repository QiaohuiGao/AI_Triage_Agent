import numpy as np
from typing import List, Dict
from .schemas import RetrievalDoc
from .config import CFG

class VectorStore:
    def __init__(self):
        self._embs=np.empty((0,CFG.vector.dim),dtype="float32")
        self._docs: List[RetrievalDoc]=[]

    def _embed(self,texts:List[str])->np.ndarray:
        rng=np.random.default_rng(7)
        return rng.standard_normal((len(texts),CFG.vector.dim)).astype("float32")

    def add(self,docs:List[Dict]):
        embs=self._embed([d["text"] for d in docs])
        self._embs=np.vstack([self._embs,embs])
        self._docs.extend([RetrievalDoc(id=d["id"],text=d["text"],score=0.0,meta=d.get("meta",{})) for d in docs])

    def search(self,query:str,k:int)->List[RetrievalDoc]:
        if len(self._docs)==0: return []
        q=self._embed([query])[0]
        norms=(np.linalg.norm(self._embs,axis=1)*np.linalg.norm(q)+1e-9)
        sims=(self._embs@q)/norms
        idx=np.argsort(-sims)[:k]
        return [RetrievalDoc(id=self._docs[i].id,text=self._docs[i].text,score=float(sims[i]),meta=self._docs[i].meta) for i in idx]