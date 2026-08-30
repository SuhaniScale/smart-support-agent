"""
Meaning Extraction Agent
------------------------
Step 1 of the Support Ticket Pipeline.

This module takes a structured dictionary input and extracts structured meaning
using Gemini 3.1 Flash Lite, enforcing a strict JSON output schema.

It is designed to run on Google Cloud / Vertex AI using a GCP Project ID
from a .env file instead of an API key.
"""

import json
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from enum import Enum


# =====================================================================
# 1. GCP / Vertex AI Configuration
# =====================================================================

# Load environment variables from .env
load_dotenv()

# Get the GCP Project ID from .env
PROJECT_ID = os.getenv("GCP_PROJECT_ID")

if not PROJECT_ID:
    raise ValueError(
        "GCP_PROJECT_ID not found. Please add it to your .env file."
    )

# Vertex AI location
LOCATION = "us"


# =====================================================================
# 2. Schema Definition
# =====================================================================
# We use Pydantic and Enums to define the exact structure we want.

class UrgencyLevel(str, Enum):
    """Strict enumeration for the urgency level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketExtraction(BaseModel):
    """
    The strict JSON structure required for our downstream pipeline.

    The descriptions act as direct instructions to the Gemini model.
    """
    product_area: str = Field(
        description="Which product or system does this relate to? (e.g., Mobile App, Billing, Login, Dashboard)"
    )
    issue_type: str = Field(
        description="What kind of issue is this? (e.g., Crash, Billing Error, Performance, Access Issue)"
    )
    urgency: UrgencyLevel = Field(
        description="How urgent does it sound? Choose exactly one from the enum."
    )
    region: str = Field(
        description="What geographic region is mentioned? If none is mentioned, output exactly 'unspecified'."
    )
    summary: str = Field(
        description="A concise final summary of the given ticket."
    )


# =====================================================================
# 3. Agent Core Logic
# =====================================================================

def extract_ticket_meaning(ticket_payload: dict) -> dict:
    """
    Takes a support ticket dictionary and extracts key information
    into a strictly formatted JSON string using Gemini 3.1 Flash Lite.

    Args:
        ticket_payload (dict): The input dictionary containing
                               ticket_id, raw_text, source, timestamp.

    Returns:
        str: A validated JSON string matching the TicketExtraction schema.
    """

    # Initialize the Vertex AI client using the GCP Project ID.
    # Authentication is handled through Google Cloud credentials.
    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION
    )

    # Target the specific lightweight model requested
    MODEL_ID = "gemini-3.1-flash-lite"

    # Define our system instructions to set the agent's persona and rules
    system_instruction = (
        "You are an expert support ticket extraction agent. "
        "Your job is to read raw support tickets and extract the requested fields into a valid JSON object. "
        "Adhere strictly to the requested schema. Do not include markdown formatting or extra conversational text."
    )

    # Convert the input payload back to a formatted JSON string
    # for the prompt to read cleanly
    formatted_input = json.dumps(ticket_payload, indent=2)

    prompt = (
        f"Extract the meaning from the following raw support ticket:\n\n"
        f"{formatted_input}"
    )

    try:
        # Call the model, explicitly passing the Pydantic schema
        # to enforce the JSON structure
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,

                # Force the model to return application/json
                response_mime_type="application/json",

                # Pass our strict Pydantic model to guarantee
                # the output format
                response_schema=TicketExtraction,

                # Setting a low temperature as this is a
                # deterministic extraction task
                temperature=0.1
            ),
        )

        # Return the validated JSON string directly
        return json.loads(response.text)

    except Exception as e:
        print(f"Extraction Agent Failed: {e}")
        raise


# =====================================================================
# 4. Execution Block
# =====================================================================

if __name__ == "__main__":

    # The required input format
    sample_input = {
        "ticket_id": "TCK-1049",
        "raw_text": "Our dashboard in the US-East region has been loading extremely slowly for the past 2 hours. It's causing major delays for our sales team.",
        "source": "email_support",
        "timestamp": "2026-08-16T13:00:00Z"
    }

    print("Agent is processing the ticket...\n")

    # Run the extraction
    structured_output = extract_ticket_meaning(sample_input)

    # Print the resulting JSON
    print("Resulting Structured Output:")
    print(structured_output)