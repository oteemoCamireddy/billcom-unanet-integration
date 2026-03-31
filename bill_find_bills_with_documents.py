import json
from pathlib import Path
import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE = os.getenv("BILL_API_BASE", "https://api.bill.com").rstrip("/")
ORG_ID = os.getenv("BILL_ORG_ID")
DEV_KEY = os.getenv("BILL_DEV_KEY")
USERNAME = os.getenv("BILL_USERNAME")
PASSWORD = os.getenv("BILL_PASSWORD")

TIMEOUT = 30


def login():
    url = f"{BASE}/api/v2/Login.json"
    payload = {
        "devKey": DEV_KEY,
        "userName": USERNAME,
        "password": PASSWORD,
        "orgId": ORG_ID,
    }

    r = requests.post(url, data=payload, timeout=TIMEOUT)
    data = r.json()

    session_id = data.get("sessionId") or data.get("response_data", {}).get("sessionId")
    if not session_id:
        raise SystemExit("Login failed")

    print("Login success")
    return session_id


def get_documents(session_id, bill_id):
    url = f"{BASE}/api/v2/GetDocuments.json"

    payload = {
        "devKey": DEV_KEY,
        "sessionId": session_id,
        "data": json.dumps({
            "id": bill_id,
            "start": 0,
            "max": 20
        })
    }

    r = requests.post(url, data=payload, timeout=TIMEOUT)
    return r.json()


def main():
    session_id = login()

    bill_ids_file = Path("downloads/bill_ids.txt")
    bill_ids = [line.strip() for line in bill_ids_file.read_text().splitlines() if line.strip()]

    output_file = Path("downloads/bill_ids_with_docs.txt")

    bills_with_docs = []

    for i, bill_id in enumerate(bill_ids[:200]):  # check first 200
        print(f"Checking bill {i+1}: {bill_id}")

        data = get_documents(session_id, bill_id)
        documents = data.get("response_data", {}).get("documents", [])

        if documents:
            print("FOUND DOCUMENTS")
            bills_with_docs.append(bill_id)

    with open(output_file, "w") as f:
        for bill_id in bills_with_docs:
            f.write(bill_id + "\n")

    print(f"\nSaved {len(bills_with_docs)} bills with documents to {output_file}")


if __name__ == "__main__":
    main()