import json
import time
import random
from pathlib import Path

from google.api_core.exceptions import (
    ResourceExhausted,
    ServiceUnavailable,
    DeadlineExceeded,
)

from meaning_extraction_agent import extract_ticket_meaning

ROOT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT_DIR.parent
INPUT_FILE = str(PROJECT_ROOT / "data" / "sample_tickets.json")
OUTPUT_FILE = str(PROJECT_ROOT / "data" / "extracted_output.json")  


MAX_RETRIES = 15
BASE_DELAY = 2          # seconds
MAX_DELAY = 60          # seconds


def save_results(results):
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)


def extract_with_retry(raw_text):

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return extract_ticket_meaning(raw_text)

        except (ResourceExhausted,
                ServiceUnavailable,
                DeadlineExceeded) as e:

            wait = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)
            wait += random.uniform(0, 2)

            print(
                f"   Retry {attempt}/{MAX_RETRIES}"
                f" after {wait:.1f}s "
                f"({type(e).__name__})"
            )

            time.sleep(wait)

    raise RuntimeError("Maximum retries exceeded.")


def run_batch_extraction():

    with open(INPUT_FILE, "r") as f:
        tickets = json.load(f)

    results = []

    for ticket in tickets:

        ticket_id = ticket["ticket_id"]
        raw_text = ticket["raw_text"]

        print(f"\nProcessing {ticket_id}")

        try:

            extraction = extract_with_retry(raw_text)

            extraction["ticket_id"] = ticket_id
            results.append(extraction)

            save_results(results)

            print(
                f"   SUCCESS -> "
                f"{extraction['product_area']} / "
                f"{extraction['issue_type']} / "
                f"{extraction['urgency']}"
            )

        except Exception as e:

            print(f"   FAILED -> {e}")

    save_results(results)

    print(f"\nFinished {len(results)}/{len(tickets)}")


if __name__ == "__main__":
    run_batch_extraction()