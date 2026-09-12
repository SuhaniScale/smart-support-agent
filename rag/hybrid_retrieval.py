import os
import json
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types
from rank_bm25 import BM25Okapi
from pathlib import Path

# ==========================================================
# Locate project root and load .env
# ==========================================================

script_path = Path(__file__).resolve()

repo_root = None
for parent in [script_path, *script_path.parents]:
    if (parent / ".env").exists():
        repo_root = parent
        break

if repo_root is None:
    repo_root = script_path.parents[2]

load_dotenv(repo_root / ".env")

# ==========================================================
# Auth: Application Default Credentials only.
# Locally:    gcloud auth application-default login
# Cloud Run:  uses its attached service account automatically
# No service-account-key.json needed anywhere.
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent

# ==========================================================
# Configuration
# ==========================================================

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = "us-east1"
GEMINI_MODEL_NAME = "gemini-2.5-flash"
DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "ebc-firestone")
EMBEDDING_MODEL_NAME = "text-embedding-004"

# NOTE: this filename now matches the local output filename that
# generate_embeddings.py actually writes (OUTPUT_LOCAL_FILE). Before,
# this script was looking for "embeddings_output.json" while
# generate_embeddings.py was writing "embeddingsw2_output.json" —
# that mismatch would have made this fail to find the file.
EMBEDDINGS_FILE = BASE_DIR / "embeddingsw2_output.json"
INCIDENTS_FILE = BASE_DIR.parent / "data" / "historical_incidents.json"

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)


def load_stored_embeddings() -> dict:
    """Loads the pre-computed embeddings saved locally by generate_embeddings.py."""
    embeddings = {}
    with open(EMBEDDINGS_FILE, "r") as f:
        for line in f:
            record = json.loads(line)
            embeddings[record["id"]] = record["embedding"]
    return embeddings


def load_incidents() -> dict:
    with open(INCIDENTS_FILE, "r") as f:
        return {i["incident_id"]: i for i in json.load(f)}


def cosine_similarity(vec_a, vec_b) -> float:
    a = np.array(vec_a)
    b = np.array(vec_b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def embed_query(query: str) -> list[float]:
    response = client.models.embed_content(
        model=EMBEDDING_MODEL_NAME,
        contents=query,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    return response.embeddings[0].values


def semantic_search(query: str, embeddings: dict, top_k: int = 5) -> list[str]:
    query_embedding = embed_query(query)
    scored = [(iid, cosine_similarity(query_embedding, vec)) for iid, vec in embeddings.items()]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [iid for iid, _ in scored[:top_k]]


def keyword_search(query: str, incidents: dict, top_k: int = 5) -> list[str]:
    ids = list(incidents.keys())
    corpus = [incidents[i]["summary"].lower().split() for i in ids]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(query.lower().split())
    scored = list(zip(ids, scores))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [iid for iid, _ in scored[:top_k]]


def rerank_with_gemini(query: str, candidate_ids: list[str], incidents: dict, keep_top: int = 3) -> list[dict]:
    """Uses Gemini as a re-ranker: given a merged candidate pool, reorder by true relevance."""
    candidates_text = "\n".join(
        f"[{cid}] {incidents[cid]['summary']}" for cid in candidate_ids
    )

    prompt = f"""
You are re-ranking search results for relevance.

Query: "{query}"

Candidate historical incidents:
{candidates_text}

Rank these candidates from MOST to LEAST relevant to the query. Respond with ONLY a
valid JSON array of incident IDs in ranked order, most relevant first, like:
["H001", "H010", "H007"]
"""
    response = client.models.generate_content(
        model=GEMINI_MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    ranked_ids = json.loads(response.text)

    results = []
    for cid in ranked_ids[:keep_top]:
        if cid in incidents:
            results.append({
                "incident_id": cid,
                "summary": incidents[cid]["summary"],
                "outcome": incidents[cid]["outcome"],
            })
    return results


def hybrid_retrieve(query: str, top_k_per_method: int = 5, final_top_k: int = 3) -> list[dict]:
    embeddings = load_stored_embeddings()
    incidents = load_incidents()

    semantic_ids = semantic_search(query, embeddings, top_k_per_method)
    keyword_ids = keyword_search(query, incidents, top_k_per_method)

    merged_ids = list(dict.fromkeys(semantic_ids + keyword_ids))  # de-duplicated union

    reranked = rerank_with_gemini(query, merged_ids, incidents, keep_top=final_top_k)
    return reranked


if __name__ == "__main__":
    test_query = "weird stuff happening with people's monthly payments"

    print("=== Semantic search only (Week 2 baseline) ===")
    embeddings = load_stored_embeddings()
    incidents = load_incidents()
    semantic_only = semantic_search(test_query, embeddings, top_k=3)
    for iid in semantic_only:
        print(f"  [{iid}] {incidents[iid]['summary']}")

    print("\n=== Hybrid search + Gemini re-ranking (Week 5 upgrade) ===")
    hybrid_results = hybrid_retrieve(test_query)
    for r in hybrid_results:
        print(f"  [{r['incident_id']}] {r['summary']}")