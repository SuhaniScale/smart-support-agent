import os
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.cloud import firestore

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = os.getenv("GCP_LOCATION", "us-east1")
DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "epcdb")
EMBEDDING_MODEL_NAME = "text-embedding-004"
SIMILARITY_THRESHOLD = 0.75

# Linkage criterion used to decide "how similar is this new ticket to an
# existing cluster" — matches the same choice you'd pass to
# sklearn.cluster.AgglomerativeClustering(linkage=...).
#   "average"  -> mean similarity to every ticket in the cluster (default)
#   "complete" -> similarity to the FARTHEST ticket in the cluster (most conservative)
#   "single"   -> similarity to the CLOSEST ticket in the cluster (most permissive)
LINKAGE = os.getenv("CLUSTERING_LINKAGE", "average")

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)


def get_embedding(text: str) -> list[float]:
    result = client.models.embed_content(
        model=EMBEDDING_MODEL_NAME,
        contents=text,
    )
    return result.embeddings[0].values

def get_ticket_embedding(ticket_id: str, ticket_doc: dict | None = None) -> list[float]:
    """Embedding for a ticket, cached on the Firestore doc so repeat linkage
    comparisons (average/complete linkage touch every member) don't re-call
    the embedding model over and over."""
    ticket_ref = db.collection("tickets").document(ticket_id)
    if ticket_doc is None:
        ticket_doc = ticket_ref.get().to_dict()

    if "embedding" in ticket_doc:
        return ticket_doc["embedding"]

    # Fallback to 'summary' if 'raw_text' is missing (e.g. for migrated historical tickets)
    text_to_embed = ticket_doc.get("raw_text") or ticket_doc.get("summary")
    if not text_to_embed:
        raise KeyError(f"Ticket {ticket_id} is missing both 'raw_text' and 'summary' fields.")

    embedding = get_embedding(text_to_embed)
    ticket_ref.update({"embedding": embedding})
    return embedding


def cosine_similarity(vec_a, vec_b) -> float:
    a = np.array(vec_a)
    b = np.array(vec_b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def cluster_linkage_similarity(new_embedding: list[float], cluster: dict) -> float:
    """Similarity between a new ticket and an existing cluster, using every
    member of the cluster (not just a single representative) — this is what
    makes assignment consistent with how the cluster was originally built
    via agglomerative clustering."""
    similarities = [
        cosine_similarity(new_embedding, get_ticket_embedding(ticket_id))
        for ticket_id in cluster["ticket_ids"]
    ]

    if LINKAGE == "complete":
        return min(similarities)
    if LINKAGE == "single":
        return max(similarities)
    return sum(similarities) / len(similarities)  # "average" (default)


def assign_ticket_to_cluster(ticket_id: str, raw_text: str) -> str:
    new_embedding = get_embedding(raw_text)

    existing_clusters = list(db.collection("clusters").stream())

    best_cluster_id = None
    best_score = 0.0

    for cluster_doc in existing_clusters:
        cluster = cluster_doc.to_dict()
        similarity = cluster_linkage_similarity(new_embedding, cluster)

        if similarity >= SIMILARITY_THRESHOLD and similarity > best_score:
            best_cluster_id = cluster_doc.id
            best_score = similarity

    if best_cluster_id:
        cluster_ref = db.collection("clusters").document(best_cluster_id)
        cluster = cluster_ref.get().to_dict()
        updated_ticket_ids = cluster["ticket_ids"] + [ticket_id]
        cluster_ref.update({
            "ticket_ids": updated_ticket_ids,
            "ticket_count": len(updated_ticket_ids),
        })
        return best_cluster_id

    existing_ids = [doc.id for doc in existing_clusters]
    next_number = len(existing_ids) + 1
    new_cluster_id = f"C{next_number:03d}"

    # Cache the new ticket's embedding too, so it's ready when a future
    # ticket is compared against this new cluster.
    db.collection("tickets").document(ticket_id).update({"embedding": new_embedding})

    db.collection("clusters").document(new_cluster_id).set({
        "cluster_id": new_cluster_id,
        "ticket_count": 1,
        "ticket_ids": [ticket_id],
        "summary": raw_text[:100],
        "review_status": "pending",
    })
    return new_cluster_id