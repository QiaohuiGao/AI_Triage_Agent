import os
import json
import numpy as np
import psycopg2
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

import faiss
from openai import OpenAI


# =========================
# Config from ENV
# =========================
PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "triage")
PG_USER = os.getenv("PG_USER", "qiaohui")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "index/faiss_tbi.index")
FAISS_IDMAP_PATH = os.getenv("FAISS_IDMAP_PATH", "index/id_map.npy")  # np.int64 array of DB ids

# v2.1: Additional FAISS indexes for clinical rules
CLINICAL_RULES_INDEX_PATH = os.getenv("CLINICAL_RULES_INDEX_PATH", "index/faiss_clinical_rules.index")
CLINICAL_RULES_IDMAP_PATH = os.getenv("CLINICAL_RULES_IDMAP_PATH", "index/clinical_rules_id_map.npy")


# =========================
# Utils
# =========================
@contextmanager
def pg_conn():
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@dataclass
class RetrievalDoc:
    id: int
    title: str
    section: str
    source: str
    level: Optional[str]
    url: Optional[str]
    pub_date: Optional[str]
    text: str
    score: float
    route: str              # "faiss" | "bm25" | "fusion"
    # 可选增强字段
    tags: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # dataclass -> 纯 JSON
        return d


def rrf_fusion(rank_lists: List[List[Tuple[int, float]]], k: int = 10, K: int = 60) -> List[Tuple[int, float]]:
    """
    Reciprocal Rank Fusion:
    rank_lists: [ [(doc_id, score), ...], ...]
    Return: fused top-k of (doc_id, fused_score)
    """
    fused = {}
    for lst in rank_lists:
        for r, (doc_id, _score) in enumerate(lst):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (K + r + 1)
    out = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:k]
    return out


# =========================
# Hybrid Retriever
# =========================
class HybridRetriever:
    def __init__(self, use_clinical_rules_index: bool = True):
        """
        Initialize HybridRetriever with optional clinical rules index.

        Args:
            use_clinical_rules_index: Whether to also search the clinical rules FAISS index
        """
        # OpenAI client
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.client = OpenAI(api_key=OPENAI_API_KEY)

        # Primary FAISS index (TBI / medical guidelines)
        if not os.path.exists(FAISS_INDEX_PATH):
            raise FileNotFoundError(f"FAISS index not found: {FAISS_INDEX_PATH}")
        self.index = faiss.read_index(FAISS_INDEX_PATH)

        self.id_map = None
        if os.path.exists(FAISS_IDMAP_PATH):
            try:
                self.id_map = np.load(FAISS_IDMAP_PATH)
            except Exception:
                self.id_map = None
        if self.id_map is None:
            print("⚠️  FAISS_IDMAP_PATH 不存在或无法读取，将使用 DB 顺序兜底匹配")

        # v2.1: Clinical rules FAISS index (optional)
        self.use_clinical_rules_index = use_clinical_rules_index
        self.clinical_rules_index = None
        self.clinical_rules_id_map = None

        if use_clinical_rules_index and os.path.exists(CLINICAL_RULES_INDEX_PATH):
            try:
                self.clinical_rules_index = faiss.read_index(CLINICAL_RULES_INDEX_PATH)
                if os.path.exists(CLINICAL_RULES_IDMAP_PATH):
                    self.clinical_rules_id_map = np.load(CLINICAL_RULES_IDMAP_PATH)
                print(f"✅ Clinical rules FAISS index loaded: {self.clinical_rules_index.ntotal} vectors")
            except Exception as e:
                print(f"⚠️  Failed to load clinical rules FAISS index: {e}")

    # 生成查询向量
    def _embed(self, text: str) -> np.ndarray:
        resp = self.client.embeddings.create(model=OPENAI_EMBED_MODEL, input=[text])
        vec = np.array(resp.data[0].embedding, dtype="float32")
        return vec

    # FAISS 召回
    def _faiss_search(self, query: str, topk: int = 20) -> List[Tuple[int, float]]:
        qv = self._embed(query)
        qv = np.expand_dims(qv, axis=0)
        D, I = self.index.search(qv, topk)  # distances, indices
        I = I[0].tolist()
        D = D[0].tolist()

        # FAISS 通常返回的是 L2 距离或内积距离，这里简单转成相似度（越大越相似）
        # 如果是 IndexFlatIP（内积），D 越大越相似，可直接用；如果是 L2，则相似度 = -distance
        # 这里做一个鲁棒处理：相似度 = -distance
        cand = []
        for rank, (idx, dist) in enumerate(zip(I, D)):
            if idx < 0:
                continue
            if self.id_map is not None:
                db_id = int(self.id_map[idx])
            else:
                # 兜底：假设索引构建按 id 升序插入
                db_id = idx + 1
            score = -float(dist)
            cand.append((db_id, score))
        return cand

    # v2.1: Clinical rules FAISS 召回
    def _clinical_rules_faiss_search(self, query: str, topk: int = 10) -> List[Tuple[int, float]]:
        """
        Search the clinical rules FAISS index.
        Returns document IDs with prefix 'CR_' to distinguish from main index.
        """
        if self.clinical_rules_index is None:
            return []

        qv = self._embed(query)
        qv = np.expand_dims(qv, axis=0)
        D, I = self.clinical_rules_index.search(qv, topk)
        I = I[0].tolist()
        D = D[0].tolist()

        cand = []
        for rank, (idx, dist) in enumerate(zip(I, D)):
            if idx < 0:
                continue
            if self.clinical_rules_id_map is not None:
                db_id = int(self.clinical_rules_id_map[idx])
            else:
                db_id = idx + 1
            # Use negative IDs to distinguish clinical rules from main index
            # These will be fetched from clinical_guidelines table
            score = -float(dist)
            cand.append((-db_id, score))  # Negative ID indicates clinical rules
        return cand

    # BM25 / 全文检索（Postgres）
    def _bm25_search(
        self,
        query: str,
        topk: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[int, float]]:
        """
        用 Postgres 的 to_tsvector / ts_rank 做一个简版“BM25-like”检索，并支持简单过滤。
        filters 例子: {"source": "NICE", "tags": ["tbi"], "since": "2020-01-01"}
        """
        filters = filters or {}
        clauses = []
        params = []

        # 全文检索：simple 配置足够；医学域也可用 english
        ts_query = query
        where = "to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(section,'') || ' ' || coalesce(text,'')) @@ plainto_tsquery('simple', %s)"
        params.append(ts_query)

        # 过滤：source
        if "source" in filters and filters["source"]:
            clauses.append("source = %s")
            params.append(filters["source"])

        # 过滤：tags 包含任一
        if "tags" in filters and filters["tags"]:
            clauses.append("tags && %s")
            params.append(filters["tags"])  # 传 list

        # 过滤：起始日期
        if "since" in filters and filters["since"]:
            clauses.append("pub_date >= %s")
            params.append(filters["since"])

        if clauses:
            where = f"({where}) AND " + " AND ".join(clauses)

        sql = f"""
            SELECT id,
                   ts_rank(to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(section,'') || ' ' || coalesce(text,'')),
                           plainto_tsquery('simple', %s)) AS rank
            FROM medical_guidelines
            WHERE {where}
            ORDER BY rank DESC
            LIMIT %s
        """

        params.insert(1, ts_query)   # 上面 rank 的 tsquery 也要同样的 query
        params.append(topk)

        results = []
        with pg_conn() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            for row in cur.fetchall():
                results.append((int(row[0]), float(row[1])))
        return results

    def _fetch_docs(self, ids: List[int]) -> Dict[int, Dict[str, Any]]:
        if not ids:
            return {}

        # Separate positive IDs (medical_guidelines) from negative IDs (clinical_guidelines)
        main_ids = [i for i in ids if i > 0]
        clinical_ids = [-i for i in ids if i < 0]

        result = {}

        # Fetch from medical_guidelines
        if main_ids:
            sql = """
                SELECT id, title, section, source, level, url, pub_date, text, tags
                FROM medical_guidelines
                WHERE id = ANY(%s)
            """
            with pg_conn() as conn:
                cur = conn.cursor()
                cur.execute(sql, (main_ids,))
                rows = cur.fetchall()

            for r in rows:
                _id, title, section, source, level, url, pub_date, text, tags = r
                result[int(_id)] = {
                    "title": title or "",
                    "section": section or "",
                    "source": source or "",
                    "level": level,
                    "url": url,
                    "pub_date": pub_date.isoformat() if pub_date else None,
                    "text": text or "",
                    "tags": tags,
                }

        # v2.1: Fetch from clinical_guidelines (if exists)
        if clinical_ids:
            try:
                sql = """
                    SELECT id, title, chunk_type as section, source,
                           'clinical_rule' as level, NULL as url, NULL as pub_date,
                           content as text, tags
                    FROM clinical_guidelines
                    WHERE id = ANY(%s)
                """
                with pg_conn() as conn:
                    cur = conn.cursor()
                    cur.execute(sql, (clinical_ids,))
                    rows = cur.fetchall()

                for r in rows:
                    _id, title, section, source, level, url, pub_date, text, tags = r
                    # Store with negative ID to maintain mapping
                    result[-int(_id)] = {
                        "title": title or "",
                        "section": section or "",
                        "source": source or "",
                        "level": level,
                        "url": url,
                        "pub_date": pub_date,
                        "text": text or "",
                        "tags": tags,
                    }
            except Exception as e:
                print(f"Warning: Failed to fetch clinical_guidelines: {e}")

        return result

    def search(
        self,
        query: str,
        topk: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        use_faiss: bool = True,
        use_bm25: bool = True,
        use_clinical_rules: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        返回 JSON 可序列化的证据列表，每条包括：text/title/section/source/score/url/pub_date 等

        Args:
            query: Search query
            topk: Number of results to return
            filters: Optional filters for BM25 search
            use_faiss: Whether to use main FAISS index
            use_bm25: Whether to use BM25 (PostgreSQL full-text search)
            use_clinical_rules: Whether to include clinical rules FAISS index
        """
        rank_lists: List[List[Tuple[int, float]]] = []
        faiss_rank = []
        bm25_rank = []
        clinical_rules_rank = []

        if use_faiss:
            try:
                faiss_rank = self._faiss_search(query, topk=topk * 2)
            except Exception as e:
                print(f"FAISS search error: {e}")

        if use_bm25:
            try:
                bm25_rank = self._bm25_search(query, topk=topk * 2, filters=filters)
            except Exception as e:
                print(f"BM25 search error: {e}")

        # v2.1: Also search clinical rules index
        if use_clinical_rules and self.use_clinical_rules_index:
            try:
                clinical_rules_rank = self._clinical_rules_faiss_search(query, topk=topk)
            except Exception as e:
                print(f"Clinical rules FAISS search error: {e}")

        if faiss_rank:
            rank_lists.append(faiss_rank)
        if bm25_rank:
            rank_lists.append(bm25_rank)
        if clinical_rules_rank:
            rank_lists.append(clinical_rules_rank)

        fused_pairs: List[Tuple[int, float]]
        route = "fusion"
        if len(rank_lists) == 0:
            fused_pairs = []
        elif len(rank_lists) == 1:
            fused_pairs = rank_lists[0][:topk]
            if faiss_rank:
                route = "faiss"
            elif bm25_rank:
                route = "bm25"
            else:
                route = "clinical_rules"
        else:
            fused_pairs = rrf_fusion(rank_lists, k=topk)

        # 取详情
        ids = [doc_id for doc_id, _ in fused_pairs]
        meta = self._fetch_docs(ids)

        # 组装 RetrievalDoc
        out: List[RetrievalDoc] = []
        score_by_id = dict(fused_pairs)
        for doc_id in ids:
            m = meta.get(doc_id)
            if not m:
                continue
            # Determine route based on doc_id sign
            doc_route = route
            if doc_id < 0:
                doc_route = "clinical_rules"
            out.append(
                RetrievalDoc(
                    id=abs(doc_id),  # Use absolute value for display
                    title=m["title"],
                    section=m["section"],
                    source=m["source"],
                    level=m["level"],
                    url=m["url"],
                    pub_date=m["pub_date"],
                    text=m["text"],
                    score=float(score_by_id.get(doc_id, 0.0)),
                    route=doc_route,
                    tags=m["tags"],
                )
            )

        # 转为 JSON-safe dict
        return [d.to_dict() for d in out]