import os
from pathlib import Path

import gradio as gr
from dotenv import load_dotenv
from google.cloud import firestore
from google.api_core.exceptions import GoogleAPICallError

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
# Local credentials only
# Cloud Run automatically uses its Service Account
# ==========================================================

# ==========================================================
# Configuration
# ==========================================================

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "epcfirestoredb")

if not PROJECT_ID:
    raise RuntimeError("GCP_PROJECT_ID not found.")

print(f"Project : {PROJECT_ID}")
print(f"Database: {DATABASE_ID}")

db = firestore.Client(
    project=PROJECT_ID,
    database=DATABASE_ID
)

# ==========================================================
# Firestore Helpers
# ==========================================================
def get_pending_cluster_ids():
    print("=" * 50, flush=True)
    print("get_pending_cluster_ids() called", flush=True)
    print("Project:", PROJECT_ID, flush=True)
    print("Database:", DATABASE_ID, flush=True)

    docs = list(db.collection("clusters").stream())

    print("Number of docs:", len(docs), flush=True)

    ids = []

    for doc in docs:
        print(doc.id, doc.to_dict(), flush=True)
        ids.append(doc.id)

    return ids

def load_cluster_details(cluster_id):

    if not cluster_id:
        return "Select a cluster."

    doc = db.collection("clusters").document(cluster_id).get()

    if not doc.exists:
        return "Cluster not found."

    data = doc.to_dict()

    return (
        f"Cluster ID: {data['cluster_id']}\n"
        f"Ticket Count: {data['ticket_count']}\n"
        f"Ticket IDs: {', '.join(data['ticket_ids'])}\n"
        f"Summary: {data['summary']}\n"
        f"Current Status: {data['review_status']}"
    )


def set_review_status(cluster_id, new_status):

    if not cluster_id:
        return (
            "No cluster selected.",
            gr.update(
                choices=get_pending_cluster_ids(),
                value=None
            ),
        )

    db.collection("clusters").document(cluster_id).update(
        {
            "review_status": new_status
        }
    )

    updated = get_pending_cluster_ids()

    return (
        f"{cluster_id} marked as {new_status}",
        gr.update(
            choices=updated,
            value=None
        ),
    )


# ==========================================================
# Initial Load
# ==========================================================

pending_clusters = get_pending_cluster_ids()

# ==========================================================
# UI
# ==========================================================

with gr.Blocks(title="EPC Platform - Admin Review Panel") as demo:

    gr.Markdown("# EPC Platform — Cluster Review Panel for Admins")

    gr.Markdown(
        "Review pending clusters before they are escalated."
    )

    cluster_dropdown = gr.Dropdown(
        choices=pending_clusters,
        label="Pending Clusters",
    )

    details_box = gr.Textbox(
        label="Cluster Details",
        lines=8,
        interactive=False,
    )

    status_box = gr.Textbox(
        label="Last Action",
        interactive=False,
    )

    with gr.Row():

        approve_btn = gr.Button("✅ Approve")

        reject_btn = gr.Button("❌ Reject")

    cluster_dropdown.change(
        fn=load_cluster_details,
        inputs=cluster_dropdown,
        outputs=details_box,
    )

    approve_btn.click(
        fn=lambda cid: set_review_status(cid, "approved"),
        inputs=cluster_dropdown,
        outputs=[status_box, cluster_dropdown],
    )

    reject_btn.click(
        fn=lambda cid: set_review_status(cid, "rejected"),
        inputs=cluster_dropdown,
        outputs=[status_box, cluster_dropdown],
    )

# ==========================================================
# Launch
# ==========================================================
# agents/deployment/admin_panel.py

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=True,
        quiet=False,
    )
