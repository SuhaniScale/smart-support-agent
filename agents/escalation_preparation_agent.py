import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.cloud import firestore, bigquery

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = os.getenv("GCP_LOCATION", "us-east1")
DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "epcdb")
MODEL_NAME = "gemini-2.5-flash"
SIGNIFICANCE_THRESHOLD = 70

REPORT_PROMPT_TEMPLATE = """
You are preparing a business escalation report for a human reviewer.

Problem cluster summary: {summary}
Number of affected tickets: {ticket_count}
Impact score: {impact_score}/100
Severity: {severity}
Scoring rationale: {rationale}

Relevant historical incidents (for context only, may or may not be related):
{historical_context}

Write a short escalation report in Markdown, under 200 words, with these sections:
## Problem
## Business Impact
## Recommended Action

Be factual and concise. If a historical incident is genuinely relevant, reference it briefly.
"""

# Old SDK: vertexai.init(...) + GenerativeModel(MODEL_NAME)
# New SDK: same Vertex AI backend (project ID + ADC auth, no API key),
# through the updated google-genai client.
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)
bq_client = bigquery.Client(project=PROJECT_ID)


def get_all_historical_incidents() -> str:
    query = "SELECT summary, outcome FROM `epcdatasetid.historical_incidents`"
    rows = bq_client.query(query).result()
    lines = [f"- {row.summary} (Outcome: {row.outcome})" for row in rows]
    return "\n".join(lines)


def prepare_escalation(cluster_id: str) -> dict | None:
    cluster_doc = db.collection("clusters").document(cluster_id).get()
    cluster = cluster_doc.to_dict()

    if cluster.get("impact_score", 0) < SIGNIFICANCE_THRESHOLD:
        print(f"{cluster_id}: below threshold ({cluster.get('impact_score', 0)}), skipping escalation.")
        return None

    historical_context = get_all_historical_incidents()

    prompt = REPORT_PROMPT_TEMPLATE.format(
        summary=cluster["summary"],
        ticket_count=cluster["ticket_count"],
        impact_score=cluster["impact_score"],
        severity=cluster["severity"],
        rationale=cluster.get("scoring_rationale", ""),
        historical_context=historical_context,
    )

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    report_markdown = response.text.strip()

    escalation_doc = {
        "cluster_id": cluster_id,
        "report_markdown": report_markdown,
        "severity": cluster["severity"],
        "impact_score": cluster["impact_score"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "review_status": "pending",
    }

    db.collection("escalations").document(cluster_id).set(escalation_doc)
    print(f"{cluster_id}: escalation report created.")
    return escalation_doc


if __name__ == "__main__":
    all_clusters = db.collection("clusters").stream()
    for doc in all_clusters:
        prepare_escalation(doc.id)