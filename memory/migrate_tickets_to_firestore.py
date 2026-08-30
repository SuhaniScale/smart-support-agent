import os
import json
from dotenv import load_dotenv
from google.cloud import firestore
from pathlib import Path

script_path = Path(__file__).resolve()
repo_root = None
for parent in [script_path, *script_path.parents]:
    if (parent / ".env").exists():
        repo_root = parent
        break

if repo_root is None:
    repo_root = script_path.parents[2]

dotenv_path = repo_root / ".env"
load_dotenv(dotenv_path)

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "epcfirestoredb")

if not PROJECT_ID:
    raise RuntimeError("Set GCP_PROJECT_ID in your .env file before running this script.")

TICKETS_FILE = repo_root / "data" / "extracted_output.json"
CLUSTERS_FILE = repo_root / "data" / "clusters_output.json"

print(f"Using Firestore project: {PROJECT_ID}")
print(f"Using Firestore database: {DATABASE_ID}")
db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)


def build_ticket_to_cluster_map(clusters: list[dict]) -> dict:
    """Returns a dict mapping ticket_id -> cluster_id, using Week 2's cluster output."""
    mapping = {}
    for cluster in clusters:
        for ticket_id in cluster["ticket_ids"]:
            mapping[ticket_id] = cluster["cluster_id"]
    return mapping


def migrate_tickets():
    if not TICKETS_FILE.exists():
        raise FileNotFoundError(f"Tickets file not found: {TICKETS_FILE}")
    if not CLUSTERS_FILE.exists():
        raise FileNotFoundError(
            f"Clusters file not found: {CLUSTERS_FILE}. Run the clustering agent first."
        )

    with open(TICKETS_FILE, "r", encoding="utf-8") as f:
        tickets = json.load(f)

    with open(CLUSTERS_FILE, "r", encoding="utf-8") as f:
        clusters = json.load(f)

    ticket_to_cluster = build_ticket_to_cluster_map(clusters)

    for ticket in tickets:
        ticket_id = ticket["ticket_id"]
        ticket["cluster_id"] = ticket_to_cluster.get(ticket_id, "UNASSIGNED")

        doc_ref = db.collection("tickets").document(ticket_id)
        doc_ref.set(ticket)
        print(f"Migrated {ticket_id} -> cluster {ticket['cluster_id']}")

    print(f"\nDone. Migrated {len(tickets)} tickets into Firestore.")


if __name__ == "__main__":
    migrate_tickets()