from dotenv import load_dotenv
load_dotenv()

import os
from fastapi.testclient import TestClient
from main import app
from models import OpportunityInput

client = TestClient(app)

def test_evaluate_endpoint():
    # Only run this test if env vars are present, otherwise just print a message
    if not os.environ.get("GEMINI_API_KEY") or not os.environ.get("SUPABASE_URL"):
        print("Skipping full evaluation test because GEMINI_API_KEY or SUPABASE_URL is missing.")
        print("Please configure .env file and run `pytest test_pipeline.py -s` to test.")
        return

    sample_opportunity = """
    Software Engineering Intern at TechCorp.
    Duration: 6 months.
    Stipend: $3000/month.
    Requirements: Python, React, and a passion for building AI products.
    Location: New York, USA (Relocation required).
    """

    payload = {
        "raw_text": sample_opportunity,
        "source_url": "https://example.com/job/123",
        "source_name": "Test Script",
        "source_tier": "TIER_1_TRUSTED"
    }

    print("Sending evaluation request to /evaluate...")
    response = client.post("/evaluate", json=payload)
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("Evaluation successful!")
        print("Match Score:", data['evaluation']['match_score'])
        print("Pros:", data['evaluation']['pros'])
        print("Cons:", data['evaluation']['cons'])
        print("Schedule Conflict:", data['evaluation']['schedule_conflict'])
    else:
        print("Error:", response.text)

if __name__ == "__main__":
    test_evaluate_endpoint()
