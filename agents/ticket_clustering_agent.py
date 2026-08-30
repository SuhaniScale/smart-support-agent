import os
import json
import numpy as np
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.api_core import exceptions as api_exceptions
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_distances

# ============================================================
# AUTH NOTE:
# No service-account-key.json needed anymore. Auth comes from
# Application Default Credentials (ADC) — set up once by running:
#
#     gcloud auth application-default login
#
# The genai Client automatically finds and uses those credentials.
# ============================================================

repo_root = Path(__file__).resolve().parent
dotenv_path = repo_root / ".env"
load_dotenv(dotenv_path)

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = "us-east1"
EMBEDDING_MODEL_NAME = "text-embedding-004"

# Agglomerative clustering groups tickets by how close their embeddings
# are, merging the closest pairs/groups first and stopping once nothing
# is closer than this distance. Distance = 1 - cosine_similarity, so a
# similarity threshold of 0.75 becomes a distance threshold of 0.25.
SIMILARITY_THRESHOLD = 0.75
DISTANCE_THRESHOLD = 1 - SIMILARITY_THRESHOLD

ROOT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT_DIR.parent
TICKETS_FILE = str(PROJECT_ROOT / "data" / "sample_tickets.json")

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)


def embed_all_tickets(tickets: list[dict]) -> dict:
    """Returns a dict mapping ticket_id -> embedding vector."""
    embeddings = {}
    texts = [t["raw_text"] for t in tickets]
    ids = [t["ticket_id"] for t in tickets]

    batch_size = 8

    def get_embeddings_with_retry(batch_texts, max_retries=3, initial_delay=2):
        attempt = 0
        while attempt < max_retries:
            try:
                response = client.models.embed_content(
                    model=EMBEDDING_MODEL_NAME,
                    contents=batch_texts,
                    config=types.EmbedContentConfig(task_type="CLUSTERING"),
                )
                return [e.values for e in response.embeddings]
            except api_exceptions.ResourceExhausted:
                attempt += 1
                if attempt >= max_retries:
                    raise
                delay = initial_delay * (2 ** (attempt - 1))
                print(f"Quota exhausted, retrying in {delay}s (attempt {attempt}/{max_retries})")
                time.sleep(delay)

    pos = 0
    while pos < len(texts):
        end = min(pos + batch_size, len(texts))
        batch = texts[pos:end]
        batch_ids = ids[pos:end]

        vectors = get_embeddings_with_retry(batch)

        for tid, vec in zip(batch_ids, vectors):
            embeddings[tid] = vec

        pos = end

    return embeddings


def cluster_tickets(tickets: list[dict]) -> list[dict]:
    """
    Groups tickets by embedding similarity using agglomerative clustering.
    Each ticket starts as its own cluster; the closest clusters keep
    merging until no two clusters are closer than DISTANCE_THRESHOLD.
    """
    embeddings = embed_all_tickets(tickets)
    ticket_ids = [t["ticket_id"] for t in tickets]

    # Build the matrix of vectors in the same order as ticket_ids
    vectors = np.array([embeddings[tid] for tid in ticket_ids])

    # Precompute pairwise cosine distance (1 - cosine similarity) so
    # AgglomerativeClustering merges based on the same signal we used before
    distance_matrix = cosine_distances(vectors)

    clustering_model = AgglomerativeClustering(
        n_clusters=None,
        metric="precomputed",
        linkage="average",
        distance_threshold=DISTANCE_THRESHOLD,
    )
    labels = clustering_model.fit_predict(distance_matrix)

    # Group ticket_ids by the cluster label sklearn assigned them
    clusters_by_label: dict[int, list[str]] = {}
    for ticket_id, label in zip(ticket_ids, labels):
        clusters_by_label.setdefault(int(label), []).append(ticket_id)

    output = []
    for i, (label, member_ids) in enumerate(clusters_by_label.items(), start=1):
        output.append({
            "cluster_id": f"C{i:03d}",
            "ticket_count": len(member_ids),
            "ticket_ids": member_ids,
        })
    return output


if __name__ == "__main__":
    with open(TICKETS_FILE, "r") as f:
        tickets = json.load(f)

    clusters = cluster_tickets(tickets)

    print(f"Formed {len(clusters)} clusters from {len(tickets)} tickets:\n")
    for cluster in clusters:
        print(f"{cluster['cluster_id']} ({cluster['ticket_count']} tickets): {cluster['ticket_ids']}")

    output_path = PROJECT_ROOT / "data" / "clusters_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(clusters, f, indent=2)
    print(f"\nSaved cluster results to {output_path}")
