import os
import json
from pathlib import Path
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv

load_dotenv()

BASE = os.getenv("BILL_API_BASE", "https://api.bill.com").rstrip("/")
WEB_BASE = os.getenv("BILL_WEB_BASE", "https://app01.us.bill.com").rstrip("/")
ORG_ID = os.getenv("BILL_ORG_ID")
DEV_KEY = os.getenv("BILL_DEV_KEY")
USERNAME = os.getenv("BILL_USERNAME")
PASSWORD = os.getenv("BILL_PASSWORD")

TIMEOUT = 30
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)


def must_env():
    missing = [k for k, v in {
        "BILL_ORG_ID": ORG_ID,
        "BILL_DEV_KEY": DEV_KEY,
        "BILL_USERNAME": USERNAME,
        "BILL_PASSWORD": PASSWORD,
        "BILL_WEB_BASE": WEB_BASE,
    }.items() if not v]

    if missing:
        raise SystemExit(f"Missing in .env: {', '.join(missing)}")


def login_get_session():
    url = f"{BASE}/api/v2/Login.json"
    payload = {
        "devKey": DEV_KEY,
        "userName": USERNAME,
        "password": PASSWORD,
        "orgId": ORG_ID,
    }

    r = requests.post(url, data=payload, timeout=TIMEOUT)

    try:
        data = r.json()
    except Exception:
        raise SystemExit(f"Login response is not JSON. Status={r.status_code}, Body={r.text[:500]}")

    if data.get("response_status") == 1:
        raise SystemExit(f"Login failed: {data}")

    session_id = data.get("sessionId") or data.get("response_data", {}).get("sessionId")
    if not session_id:
        raise SystemExit(f"Login did not return sessionId: {data}")

    print("✅ Login success. sessionId prefix:", session_id[:6], "...")
    return session_id


def list_bills_page(session_id, start=0, max_records=50):
    url = f"{BASE}/api/v2/List/Bill.json"

    payload = {
        "devKey": DEV_KEY,
        "sessionId": session_id,
        "data": json.dumps({
            "start": start,
            "max": max_records
        })
    }

    r = requests.post(url, data=payload, timeout=TIMEOUT)

    try:
        data = r.json()
    except Exception:
        raise SystemExit(f"List/Bill response is not JSON. Status={r.status_code}, Body={r.text[:500]}")

    if data.get("response_status") == 1:
        raise SystemExit(f"List bills failed: {data}")

    return data.get("response_data", [])


def get_bill_documents(session_id, bill_id):
    url = f"{BASE}/api/v2/GetDocuments.json"
    payload = {
        "devKey": DEV_KEY,
        "sessionId": session_id,
        "data": json.dumps({
            "id": bill_id,
            "start": 0,
            "max": 10
        })
    }

    r = requests.post(url, data=payload, timeout=TIMEOUT)

    try:
        data = r.json()
    except Exception:
        raise SystemExit(f"GetDocuments response is not JSON. Status={r.status_code}, Body={r.text[:500]}")

    if data.get("response_status") == 1:
        raise SystemExit(f"GetDocuments failed for bill {bill_id}: {data}")

    return data.get("response_data", {})


def find_first_bill_with_documents(session_id, page_size=50, max_pages=5):
    """
    Search bills until we find one that has attached documents.
    """
    for page in range(max_pages):
        start = page * page_size
        bills = list_bills_page(session_id, start=start, max_records=page_size)

        print(f"\nChecking page {page + 1} (start={start}) -> {len(bills)} bill(s)")

        if not bills:
            break

        for i, bill in enumerate(bills, start=1):
            bill_id = bill.get("id")
            invoice_number = str(bill.get("invoiceNumber", "")).strip() or "N/A"

            print(f"  [{i}] Checking invoice {invoice_number} (bill_id={bill_id})")

            docs_response = get_bill_documents(session_id, bill_id)
            doc_list = docs_response.get("documents", [])

            if doc_list:
                print(f"✅ Found attached document(s) for invoice {invoice_number}")
                return bill, docs_response

    return None, None


def make_absolute_file_url(file_url: str) -> str:
    """
    Bill.com sometimes returns a relative URL like /FileServlet?id=...
    Convert it to a full URL using BILL_WEB_BASE.
    """
    if file_url.startswith("http://") or file_url.startswith("https://"):
        return file_url

    return urljoin(WEB_BASE, file_url)


def download_file(file_url, output_path):
    full_url = make_absolute_file_url(file_url)
    print("Downloading from:", full_url)

    r = requests.get(full_url, timeout=TIMEOUT)
    r.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(r.content)

    print(f"✅ Downloaded: {output_path}")


def main():
    must_env()
    session_id = login_get_session()

    target_bill, docs_response = find_first_bill_with_documents(
        session_id=session_id,
        page_size=50,
        max_pages=5
    )

    if not target_bill:
        print("\n❌ No bills with attached documents were found in the searched pages.")
        return

    bill_id = target_bill.get("id")
    invoice_number = target_bill.get("invoiceNumber") or "unknown"

    print("\nUsing bill:")
    print("  bill_id =", bill_id)
    print("  invoice_number =", invoice_number)

    print("\nDocuments response preview:")
    print(json.dumps(docs_response, indent=2)[:2000])

    doc_list = docs_response.get("documents", [])
    first_doc = doc_list[0]

    print("\nFirst document metadata preview:")
    print(json.dumps(first_doc, indent=2)[:1200])

    file_url = first_doc.get("fileURL") or first_doc.get("fileUrl")
    doc_name = first_doc.get("fileName") or first_doc.get("name") or f"{invoice_number}.pdf"

    if not file_url:
        print("\n❌ fileUrl not found in document metadata.")
        return

    safe_name = doc_name.replace("/", "_").replace("\\", "_")
    output_path = DOWNLOAD_DIR / safe_name

    download_file(file_url, output_path)

    with open(DOWNLOAD_DIR / f"{invoice_number}_bill.json", "w", encoding="utf-8") as f:
        json.dump(target_bill, f, indent=2)

    with open(DOWNLOAD_DIR / f"{invoice_number}_docs.json", "w", encoding="utf-8") as f:
        json.dump(docs_response, f, indent=2)

    print("\n✅ Saved bill metadata and document metadata.")


if __name__ == "__main__":
    main()