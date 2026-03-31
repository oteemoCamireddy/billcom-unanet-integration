import os
import json
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

BASE = os.getenv("BILL_API_BASE", "https://api.bill.com").rstrip("/")
ORG_ID = os.getenv("BILL_ORG_ID")
DEV_KEY = os.getenv("BILL_DEV_KEY")
USERNAME = os.getenv("BILL_USERNAME")
PASSWORD = os.getenv("BILL_PASSWORD")

TIMEOUT = 30
DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)


def must_env():
    missing = [
        k for k, v in {
            "BILL_ORG_ID": ORG_ID,
            "BILL_DEV_KEY": DEV_KEY,
            "BILL_USERNAME": USERNAME,
            "BILL_PASSWORD": PASSWORD,
        }.items() if not v
    ]
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
    print("Login HTTP status:", r.status_code)

    try:
        data = r.json()
    except Exception:
        print("Non-JSON login response:")
        print(r.text[:500])
        raise SystemExit("Login response is not JSON")

    if data.get("response_status") == 1:
        raise SystemExit(f"Login failed:\n{json.dumps(data, indent=2)}")

    session_id = data.get("sessionId") or data.get("response_data", {}).get("sessionId")
    if not session_id:
        raise SystemExit(f"Login did not return sessionId:\n{json.dumps(data, indent=2)}")

    print("✅ Login success")
    return session_id


def extract_bill_list(response_json):
    """
    BILL list APIs sometimes return list data in slightly different shapes.
    This function tries the common possibilities safely.
    """
    response_data = response_json.get("response_data")

    if isinstance(response_data, list):
        return response_data

    if isinstance(response_data, dict):
        for key in ["bill", "bills", "billList", "data"]:
            value = response_data.get(key)
            if isinstance(value, list):
                return value

    return []


def list_bills_page(session_id, start=0, max_count=100):
    url = f"{BASE}/api/v2/List/Bill.json"

    payload = {
        "devKey": DEV_KEY,
        "sessionId": session_id,
        "data": json.dumps({
            "start": start,
            "max": max_count
        })
    }

    r = requests.post(url, data=payload, timeout=TIMEOUT)
    print(f"List HTTP status (start={start}):", r.status_code)

    try:
        data = r.json()
    except Exception:
        print("Non-JSON list response:")
        print(r.text[:500])
        raise SystemExit("List response is not JSON")

    if data.get("response_status") == 1:
        raise SystemExit(f"List bills failed:\n{json.dumps(data, indent=2)}")

    return data


def list_all_bills(session_id, page_size=100, max_pages=20):
    all_bills = []
    start = 0

    for page_no in range(max_pages):
        print(f"\nFetching bills page {page_no + 1} (start={start}, max={page_size})...")
        data = list_bills_page(session_id, start=start, max_count=page_size)
        bills = extract_bill_list(data)

        if not bills:
            print("No more bills returned.")
            break

        print(f"Fetched {len(bills)} bills")
        all_bills.extend(bills)

        if len(bills) < page_size:
            print("Last page reached.")
            break

        start += page_size

    return all_bills


def save_outputs(all_bills):
    raw_file = DOWNLOADS_DIR / "bills_output.json"
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(all_bills, f, indent=2)
    print(f"Saved raw bills to {raw_file}")

    summary = []
    bill_ids = []

    for bill in all_bills:
        bill_id = bill.get("id")
        if bill_id:
            bill_ids.append(bill_id)

        summary.append({
            "id": bill.get("id"),
            "invoiceNumber": bill.get("invoiceNumber"),
            "vendorId": bill.get("vendorId"),
            "amount": bill.get("amount"),
            "invoiceDate": bill.get("invoiceDate"),
            "dueDate": bill.get("dueDate"),
            "description": bill.get("description"),
            "status": bill.get("status"),
        })

    summary_file = DOWNLOADS_DIR / "bills_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved bill summary to {summary_file}")

    ids_file = DOWNLOADS_DIR / "bill_ids.txt"
    with open(ids_file, "w", encoding="utf-8") as f:
        for bill_id in bill_ids:
            f.write(f"{bill_id}\n")
    print(f"Saved {len(bill_ids)} bill IDs to {ids_file}")


def main():
    must_env()
    session_id = login_get_session()
    all_bills = list_all_bills(session_id, page_size=100, max_pages=20)

    print(f"\n✅ Total bills fetched: {len(all_bills)}")
    if not all_bills:
        print("No bills found.")
        return

    print("\nBills response preview:")
    print(json.dumps(all_bills[:3], indent=2)[:2000])

    save_outputs(all_bills)


if __name__ == "__main__":
    main()