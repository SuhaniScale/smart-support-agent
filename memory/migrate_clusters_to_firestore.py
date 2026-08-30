import os
import json
import re
import time
import random
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.errors import ClientError
from google.cloud import firestore

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

# Resolve credentials path relative to the repo root when a relative path is provided
credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if credentials_path:
    credentials_path = Path(credentials_path)
    if not credentials_path.is_absolute():
        credentials_path = repo_root / credentials_path
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(credentials_path.resolve())

LOCATION = "us-east1"
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "epcfirestoredb")
MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3.1-flash")

if not PROJECT_ID:
    raise RuntimeError("Set GCP_PROJECT_ID in your .env file before running this script.")

TICKETS_FILE = repo_root / "data" / "sample_tickets.json"
CLUSTERS_FILE = repo_root / "data" / "clusters_output.json"

print(f"Using Firestore project: {PROJECT_ID}")
print(f"Using Firestore database: {DATABASE_ID}")

# google-genai client talking to Vertex AI (the enterprise/GCP-backed endpoint,
# replaces the older vertexai.generative_models.GenerativeModel preview API)
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "when",
    "users",
    "user",
    "issue",
    "issues",
    "app",
    "customer",
    "customers",
    "report",
    "reports",
    "reported",
    "is",
    "are",
    "a",
    "an",
    "to",
    "of",
    "on",
    "in",
    "from",
    "that",
    "this",
    "these",
    "those",
    "cannot",
    "unable",
    "problem",
    "problems",
    "error",
    "errors",
    "getting",
    "being",
    "after",
    "during",
    "while",
}


def build_fallback_summary(ticket_texts: list[str]) -> str:
    text_blob = " ".join(ticket_texts).lower()
    tokens = re.findall(r"[a-z0-9]+", text_blob)
    filtered = [token for token in tokens if token not in STOP_WORDS and len(token) > 2]
    counts = Counter(filtered)
    if not counts:
        return "Multiple customers report a recurring support issue."

    keywords = [word for word, _ in counts.most_common(4)]
    return f"Customers report recurring issues related to {' '.join(keywords)}."


def generate_cluster_summary(ticket_texts: list[str]) -> str:
    joined_texts = "\n".join(f"- {t}" for t in ticket_texts)
    prompt = f"""
The following are support tickets that have been grouped together because they
describe the same underlying problem. Write ONE short, neutral sentence summarizing
the shared problem. Do not list individual tickets, just describe the common issue.

Tickets:
{joined_texts}

One-sentence summary:
"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )
            summary = (getattr(response, "text", None) or "").strip()
            if summary:
                return summary
            break
        except ClientError as e:
            # google-genai raises ClientError for 4xx/5xx responses, including
            # 429 RESOURCE_EXHAUSTED from quota limits.
            is_rate_limited = getattr(e, "code", None) == 429
            if attempt == 2 or not is_rate_limited:
                break
            time.sleep(2 + attempt + random.uniform(0, 1))
        except Exception:
            if attempt == 2:
                break
            time.sleep(1 + attempt)

    return build_fallback_summary(ticket_texts)


def migrate_clusters():
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

    ticket_lookup = {t["ticket_id"]: t["raw_text"] for t in tickets}

    for cluster in clusters:
        cluster_id = cluster["cluster_id"]
        ticket_texts = [ticket_lookup[tid] for tid in cluster["ticket_ids"]]

        summary = generate_cluster_summary(ticket_texts)
        if not summary:
            summary = build_fallback_summary(ticket_texts)

        cluster_doc = {
            "cluster_id": cluster_id,
            "ticket_count": cluster["ticket_count"],
            "ticket_ids": cluster["ticket_ids"],
            "summary": summary,
            "review_status": "pending",
        }

        db.collection("clusters").document(cluster_id).set(cluster_doc)
        print(f"Migrated {cluster_id}: {summary}")

    print(f"\nDone. Migrated {len(clusters)} clusters into Firestore.")


if __name__ == "__main__":
    migrate_clusters()