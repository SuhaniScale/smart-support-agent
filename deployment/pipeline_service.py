import os
import sys
from pathlib import Path

# Add the project root folder (/app) to sys.path before any other custom imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from google.cloud import firestore

# ... (existing imports)
from guardrails.input_guardrails import validate_input
from guardrails.output_guardrails import validate_output

# ADD THESE MISSING IMPORTS:
from agents.meaning_extraction_agent import extract_ticket_meaning
from agents.cluster_assignment import assign_ticket_to_cluster
from agents.impact_scoring_agent import score_cluster_by_id
from agents.escalation_preparation_agent import prepare_escalation

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "epcdb")

db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

app = Flask(__name__)


def process_ticket(ticket_id, raw_text, source="pipeline", timestamp="", db_client=None):
    """Main ticket flow with input and output validation built in."""
    input_check = validate_input(raw_text)
    if not input_check["ok"]:
        return {"ok": False, "error": input_check["reason"]}

    cleaned_text = input_check["cleaned_text"]
    ticket_payload = {
        "ticket_id": ticket_id,
        "raw_text": cleaned_text,
        "source": source,
        "timestamp": timestamp,
    }

    extraction = extract_ticket_meaning(ticket_payload)

    output_check = validate_output(str(extraction))
    if not output_check["ok"]:
        return {"ok": False, "error": output_check["reason"]}

    if db_client is not None:
        db_client.collection("tickets").document(ticket_id).set({
            "ticket_id": ticket_id,
            "raw_text": cleaned_text,
            "source": source,
            "timestamp": timestamp,
            **extraction,
        })

    return {"ok": True, "ticket_id": ticket_id, "extraction": extraction}

@app.route("/extract", methods=["POST"])
def extract_endpoint():
    data = request.get_json() or {}
    ticket_id = data.get("ticket_id")
    raw_text = data.get("raw_text")

    if not ticket_id:
        return jsonify({"ok": False, "error": "ticket_id is required."}), 400

    if raw_text is None:
        return jsonify({"ok": False, "error": "raw_text is required."}), 400

    result = process_ticket(
        ticket_id=ticket_id,
        raw_text=raw_text,
        source=data.get("source", "pipeline"),
        timestamp=data.get("timestamp", ""),
        db_client=db,
    )

    if not result["ok"]:
        return jsonify({"ok": False, "error": result["error"]}), 400

    return jsonify(result)


@app.route("/cluster", methods=["POST"])
def cluster_endpoint():
    data = request.get_json() or {}
    ticket_id = data.get("ticket_id")

    if not ticket_id:
        return jsonify({"ok": False, "error": "ticket_id is required."}), 400

    ticket_doc = db.collection("tickets").document(ticket_id).get()
    if not ticket_doc.exists:
        return jsonify({"ok": False, "error": "Ticket not found."}), 404

    raw_text = ticket_doc.to_dict().get("raw_text")
    input_check = validate_input(raw_text or "")
    if not input_check["ok"]:
        return jsonify({"ok": False, "error": input_check["reason"]}), 400

    cluster_id = assign_ticket_to_cluster(ticket_id, input_check["cleaned_text"])
    output_check = validate_output(str({"ticket_id": ticket_id, "cluster_id": cluster_id}))
    if not output_check["ok"]:
        return jsonify({"ok": False, "error": output_check["reason"]}), 400

    db.collection("tickets").document(ticket_id).update({"cluster_id": cluster_id})

    return jsonify({"ok": True, "ticket_id": ticket_id, "cluster_id": cluster_id})


@app.route("/score", methods=["POST"])
def score_endpoint():
    data = request.get_json() or {}
    cluster_id = data.get("cluster_id")

    if not cluster_id:
        return jsonify({"ok": False, "error": "cluster_id is required."}), 400

    input_check = validate_input(str(cluster_id))
    if not input_check["ok"]:
        return jsonify({"ok": False, "error": input_check["reason"]}), 400

    result = score_cluster_by_id(cluster_id)
    output_check = validate_output(str({"cluster_id": cluster_id, "score_result": result}))
    if not output_check["ok"]:
        return jsonify({"ok": False, "error": output_check["reason"]}), 400

    return jsonify({"ok": True, "cluster_id": cluster_id, "score_result": result})


@app.route("/prepare", methods=["POST"])
def prepare_endpoint():
    data = request.get_json() or {}
    cluster_id = data.get("cluster_id")

    if not cluster_id:
        return jsonify({"ok": False, "error": "cluster_id is required."}), 400

    input_check = validate_input(str(cluster_id))
    if not input_check["ok"]:
        return jsonify({"ok": False, "error": input_check["reason"]}), 400

    escalation = prepare_escalation(cluster_id)
    output_check = validate_output(str({
        "cluster_id": cluster_id,
        "escalated": escalation is not None,
    }))
    if not output_check["ok"]:
        return jsonify({"ok": False, "error": output_check["reason"]}), 400

    return jsonify({
        "ok": True,
        "cluster_id": cluster_id,
        "escalated": escalation is not None,
    })


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "EPC pipeline service is running"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)