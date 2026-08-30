#!/bin/bash

cd "$(dirname "$0")"

echo "================================"
echo "Creating Python virtual environment..."
echo "================================"
python3 -m venv .venv

if [ ! -f ".venv/bin/activate" ]; then
    echo "Failed to create .venv."
    exit 1
fi

source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install google-genai

echo ""
echo "================================"
echo "Virtual environment is ready."
echo "================================"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "⚠️  gcloud CLI is not installed."
    echo ""
    echo "To install Google Cloud SDK, run:"
    echo "  curl https://sdk.cloud.google.com | bash"
    echo "  exec -l \$SHELL"
    echo ""
    echo "Or install via your package manager:"
    echo "  apt-get install google-cloud-sdk  (Ubuntu/Debian)"
    echo "  brew install google-cloud-sdk     (macOS)"
else
    echo "✓ gcloud CLI found. Authenticating to Google Cloud:"
    gcloud auth application-default login
fi

echo ""
echo "To run the agent:"
echo "  python agents/meaning_extraction_agent.py"

echo ""
