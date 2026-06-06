import math


def normalize_bm25_score(bm25: float) -> float:
    if bm25 >= 0:
        return 0.0
    return round(-bm25 / (1 + -bm25), 4)


def rerank_with_heading_boost(results: list[dict], query: str, boost_factor: float = 1.5) -> list[dict]:
    if not results:
        return []

    query_lower = query.lower()
    query_terms = query_lower.split()
    if not query_terms:
        return results

    for r in results:
        heading = (r.get("heading_path") or "").lower()
        match_count = sum(1 for t in query_terms if t in heading)
        if match_count > 0:
            boost = 1.0 + boost_factor * (match_count / len(query_terms))
            r["score"] = min(1.0, r.get("score", 0) * boost)

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results


def rrf_fuse(fts_results: list[dict], vec_results: list[dict], limit: int, k: int = 60) -> list[dict]:
    seen: dict[int, dict] = {}
    fused: dict[int, float] = {}

    for rank, r in enumerate(fts_results):
        cid = r["id"]
        r["score"] = 0.0
        r["distance"] = None
        seen[cid] = r
        fused[cid] = fused.get(cid, 0.0) + 1.0 / (k + rank + 1)

    for rank, r in enumerate(vec_results):
        cid = r["id"]
        r["score"] = 0.0
        if cid not in seen:
            seen[cid] = r
        fused[cid] = fused.get(cid, 0.0) + 1.0 / (k + rank + 1)

    for cid in fused:
        seen[cid]["score"] = round(fused[cid], 4)

    sorted_results = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
    return sorted_results[:limit]
