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
