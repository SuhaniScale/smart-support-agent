import os
import sys
from pathlib import Path
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from google.cloud import firestore

sys.path.append(str(Path(__file__).resolve().parent.parent / "agents"))

from meaning_extraction_agent import extract_ticket_meaning
from cluster_assignment import assign_ticket_to_cluster
from impact_scoring_agent import score_cluster_by_id
from escalation_preparation_agent import prepare_escalation

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "epcdb")

db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

app = Flask(__name__)


@app.route("/extract", methods=["POST"])
def extract_endpoint():
    data = request.get_json()
    ticket_id = data["ticket_id"]
    raw_text = data["raw_text"]
    ticket_payload = {
        "ticket_id": ticket_id,
        "raw_text": raw_text,
        "source": data.get("source", "pipeline"),
        "timestamp": data.get("timestamp", ""),
    }

    extraction = extract_ticket_meaning(ticket_payload)

    db.collection("tickets").document(ticket_id).set({
        "ticket_id": ticket_id,
        "raw_text": raw_text,
        "source": data.get("source", "pipeline"),
        "timestamp": data.get("timestamp", ""),
        **extraction,
    })

    return jsonify({"ticket_id": ticket_id, "extraction": extraction})


@app.route("/cluster", methods=["POST"])
def cluster_endpoint():
    data = request.get_json()
    ticket_id = data["ticket_id"]

    ticket_doc = db.collection("tickets").document(ticket_id).get()
    raw_text = ticket_doc.to_dict()["raw_text"]

    cluster_id = assign_ticket_to_cluster(ticket_id, raw_text)

    db.collection("tickets").document(ticket_id).update({"cluster_id": cluster_id})

    return jsonify({"ticket_id": ticket_id, "cluster_id": cluster_id})


@app.route("/score", methods=["POST"])
def score_endpoint():
    data = request.get_json()
    cluster_id = data["cluster_id"]

    result = score_cluster_by_id(cluster_id)

    return jsonify({"cluster_id": cluster_id, "score_result": result})


@app.route("/prepare", methods=["POST"])
def prepare_endpoint():
    data = request.get_json()
    cluster_id = data["cluster_id"]

    escalation = prepare_escalation(cluster_id)

    return jsonify({
        "cluster_id": cluster_id,
        "escalated": escalation is not None,
    })


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "EPC pipeline service is running"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)