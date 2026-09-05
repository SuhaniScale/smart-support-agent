import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError
from google.cloud import firestore
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = os.getenv("GCP_LOCATION", "us-east1")
DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "epcdb")
MODEL_NAME = "gemini-2.5-flash"

SIGNIFICANCE_THRESHOLD = 60  # score at or above this is escalation-worthy

SCORING_PROMPT_TEMPLATE = """
You are a business impact analyst at an enterprise software company.

A cluster of {ticket_count} customer support tickets has been grouped together because
they describe the same underlying problem:

Cluster summary: {summary}
Individual tickets:
{ticket_list}

Score the business impact of this problem on a scale of 0-100, and classify its severity.

Respond with ONLY a valid JSON object in this exact format:
{{
  "impact_score": <integer 0-100>,
  "severity": "Low" | "Medium" | "High" | "Critical",
  "rationale": "one or two sentences explaining the score"
}}
"""

REFLECTION_PROMPT_TEMPLATE = """
You previously scored a cluster of support tickets as follows:

Impact score: {impact_score}
Severity: {severity}
Rationale: {rationale}

Ticket count in this cluster: {ticket_count}

Review this score against this rubric:
- Low (0-30): isolated, minor inconvenience, few tickets
- Medium (31-60): moderate inconvenience, noticeable pattern
- High (61-85): significant business impact, many affected users, urgent
- Critical (86-100): severe, widespread, or revenue/trust threatening

Is the severity label consistent with the numeric score under this rubric?
Respond with ONLY a valid JSON object:
{{
  "consistent": true | false,
  "corrected_severity": "Low" | "Medium" | "High" | "Critical"
}}
"""

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)


# Helper function with Exponential Backoff retry for API calls
@retry(
    wait=wait_random_exponential(min=2, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(APIError),
    reraise=True
)
def generate_content_with_retry(prompt: str) -> str:
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return response.text


def score_cluster(cluster: dict, ticket_texts: list[str]) -> dict:
    ticket_list = "\n".join(f"- {t}" for t in ticket_texts)
    prompt = SCORING_PROMPT_TEMPLATE.format(
        ticket_count=cluster["ticket_count"],
        summary=cluster["summary"],
        ticket_list=ticket_list,
    )

    response_text = generate_content_with_retry(prompt)
    result = json.loads(response_text)

    # Self-reflection pass: check the score against a rubric before finalizing
    reflection_prompt = REFLECTION_PROMPT_TEMPLATE.format(
        impact_score=result["impact_score"],
        severity=result["severity"],
        rationale=result["rationale"],
        ticket_count=cluster["ticket_count"],
    )
    
    reflection_response_text = generate_content_with_retry(reflection_prompt)
    reflection_result = json.loads(reflection_response_text)

    if not reflection_result["consistent"]:
        result["severity"] = reflection_result["corrected_severity"]
        result["rationale"] += " (Severity adjusted after self-review for rubric consistency.)"

    return result


def score_cluster_by_id(cluster_id: str) -> dict:
    cluster_doc = db.collection("clusters").document(cluster_id).get()
    cluster = cluster_doc.to_dict()

    ticket_texts = []
    for ticket_id in cluster["ticket_ids"]:
        ticket_doc = db.collection("tickets").document(ticket_id).get()
        ticket_data = ticket_doc.to_dict() or {}
        ticket_text = ticket_data.get("raw_text") or ticket_data.get("summary")
        if not ticket_text:
            raise KeyError(
                f"Ticket {ticket_id} has neither 'raw_text' nor 'summary'"
            )
        ticket_texts.append(ticket_text)

    result = score_cluster(cluster, ticket_texts)

    db.collection("clusters").document(cluster_id).update({
        "impact_score": result["impact_score"],
        "severity": result["severity"],
        "scoring_rationale": result["rationale"],
    })

    return result


if __name__ == "__main__":
    all_clusters = db.collection("clusters").stream()
    for doc in all_clusters:
        cluster_id = doc.id
        result = score_cluster_by_id(cluster_id)
        print(f"{cluster_id}: score={result['impact_score']} severity={result['severity']}")
        print(f"  rationale: {result['rationale']}\n")
        
        # Adding a 1 second delay between clusters to avoid hitting quota limits aggressively
        time.sleep(1)