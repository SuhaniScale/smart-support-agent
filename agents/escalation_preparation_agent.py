import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from google import genai
import sys
from google.cloud import firestore

sys.path.append("../rag")
sys.path.append("../integrations")

from hybrid_retrieval import hybrid_retrieve
from drive_tool import get_drive_doc
from gmail_tool import draft_gmail
from discord_notifier import send_discord_alert

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

# ==========================================================
# Configuration
# ==========================================================

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = "us-east1"
MODEL_NAME = "gemini-2.5-flash"
DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "ebc-firestone")


SIGNIFICANCE_THRESHOLD = 60

REPORT_PROMPT_TEMPLATE = """
You are preparing a business escalation report for a human reviewer.

Problem cluster summary: {summary}
Number of affected tickets: {ticket_count}
Impact score: {impact_score}/100
Severity: {severity}
Scoring rationale: {rationale}

Relevant historical incidents:
{historical_context}

Relevant internal runbook excerpt (use only if genuinely applicable):
{runbook_excerpt}

Write a short escalation report in Markdown, under 200 words, with these sections:
## Problem
## Business Impact
## Recommended Action

Be factual and concise. Reference the runbook or historical incidents only if truly relevant.
"""

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)
db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)


def prepare_escalation(cluster_id: str) -> dict | None:
    cluster_doc = db.collection("clusters").document(cluster_id).get()
    cluster = cluster_doc.to_dict()

    if cluster.get("impact_score", 0) < SIGNIFICANCE_THRESHOLD:
        print(f"{cluster_id}: below threshold ({cluster.get('impact_score', 0)}), skipping escalation.")
        return None

    top_matches = hybrid_retrieve(cluster["summary"])
    historical_context = "\n".join(
        f"- {m['summary']} (Outcome: {m['outcome']})" for m in top_matches
    )

    runbook_excerpt = get_drive_doc("Runbook")

    prompt = REPORT_PROMPT_TEMPLATE.format(
        summary=cluster["summary"],
        ticket_count=cluster["ticket_count"],
        impact_score=cluster["impact_score"],
        severity=cluster["severity"],
        rationale=cluster.get("scoring_rationale", ""),
        historical_context=historical_context,
        runbook_excerpt=runbook_excerpt[:500],
    )

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    report_markdown = response.text.strip()

    gmail_draft_id = draft_gmail(
        to_email="stakeholder@example.com",
        subject=f"[EPC Platform] Escalation: {cluster['summary'][:60]}",
        body=report_markdown,
    )

    discord_alert_text = (
            f"🚨 New Escalation ({cluster['severity']})\n\n"
            f"**Cluster:** {cluster_id}\n"
            f"**Impact Score:** {cluster['impact_score']}/100\n"
            f"**Summary:** {cluster['summary']}"
        )

    escalation_doc = {
        "cluster_id": cluster_id,
        "report_markdown": report_markdown,
        "severity": cluster["severity"],
        "impact_score": cluster["impact_score"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "review_status": "pending",
        "gmail_draft_id": gmail_draft_id,
        "discord_message": discord_alert_text,
    }

    

    send_discord_alert(
        title="🚨 EPC Platform Escalation",
        message=discord_alert_text,
    )
    db.collection("escalations").document(cluster_id).set(escalation_doc)
    print(f"{cluster_id}: escalation report created.")
    return escalation_doc


if __name__ == "__main__":
    all_clusters = db.collection("clusters").stream()
    for doc in all_clusters:
        prepare_escalation(doc.id)