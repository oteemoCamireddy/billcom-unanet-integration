import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE = os.getenv("BILL_API_BASE", "https://api.bill.com").rstrip("/")
ORG_ID = os.getenv("BILL_ORG_ID")
DEV_KEY = os.getenv("BILL_DEV_KEY")
USERNAME = os.getenv("BILL_USERNAME")
PASSWORD = os.getenv("BILL_PASSWORD")

def main():
    missing = [k for k, v in {
        "BILL_ORG_ID": ORG_ID,
        "BILL_DEV_KEY": DEV_KEY,
        "BILL_USERNAME": USERNAME,
        "BILL_PASSWORD": PASSWORD,
    }.items() if not v]

    if missing:
        raise SystemExit(f"Missing in .env: {', '.join(missing)}")

    # Bill.com commonly uses an endpoint like /api/v2/Login.json (may vary by account)
    url = f"{BASE}/api/v2/Login.json"
    payload = {
        "devKey": DEV_KEY,
        "userName": USERNAME,
        "password": PASSWORD,
        "orgId": ORG_ID,
    }

    print(f"POST {url}")
    resp = requests.post(url, data=payload, timeout=30)
    print("Status:", resp.status_code)

    try:
        data = resp.json()
    except Exception:
        print(resp.text[:500])
        raise SystemExit("Response is not JSON")

    # Bill.com returns a sessionId on success in many setups
    if resp.status_code == 200 and ("sessionId" in data or data.get("response_data", {}).get("sessionId")):
        session_id = data.get("sessionId") or data["response_data"]["sessionId"]
        print("✅ Login success. sessionId obtained.")
        print("sessionId (first 6 chars):", session_id[:6], "...")
    else:
        print("❌ Login failed. Response:")
        print(data)

if __name__ == "__main__":
    main()