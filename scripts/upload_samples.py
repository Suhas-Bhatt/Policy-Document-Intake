"""
Uploads every PDF in sample_documents/ to the running Flask API, so you can
exercise POST /api/documents/upload without hand-typing curl for each file.

Usage:
    python run.py                        # in one terminal
    python scripts/upload_samples.py      # in another

Requires FLASK_BASE_URL's server to be reachable and API_GATEWAY_UPLOAD_URL
to be configured in .env (a real API Gateway endpoint) -- this script only
drives the Flask side; it does not fake out AWS.
"""
import glob
import os

import requests

FLASK_BASE_URL = os.environ.get("FLASK_BASE_URL", "http://localhost:5000")
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_documents")


def login():
    response = requests.post(
        f"{FLASK_BASE_URL}/api/auth/login",
        json={"username": "test-agent", "role": "agent"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def upload(token, filepath):
    filename = os.path.basename(filepath)
    customer_id = filename.split("_")[0]

    with open(filepath, "rb") as f:
        response = requests.post(
            f"{FLASK_BASE_URL}/api/documents/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (filename, f, "application/pdf")},
            data={"customer_id": customer_id},
            timeout=30,
        )
    return response


def main():
    token = login()
    pdfs = sorted(glob.glob(os.path.join(SAMPLE_DIR, "*.pdf")))
    if not pdfs:
        print(f"No PDFs found in {SAMPLE_DIR}. Run scripts/generate_sample_pdfs.py first.")
        return

    for path in pdfs:
        response = upload(token, path)
        print(f"{os.path.basename(path)}: {response.status_code} {response.text}")


if __name__ == "__main__":
    main()
