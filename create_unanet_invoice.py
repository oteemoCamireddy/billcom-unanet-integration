import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

UNANET_BASE = os.getenv("UNANET_BASE_URL", "").rstrip("/")
UNANET_USERNAME = os.getenv("UNANET_USERNAME")
UNANET_PASSWORD = os.getenv("UNANET_PASSWORD")

DOWNLOAD_DIR = Path("downloads")


def require_env(name: str, value: str | None) -> str:
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def load_payload() -> dict:
    payload_file = DOWNLOAD_DIR / "unanet_invoice_payload.json"

    if not payload_file.exists():
        raise SystemExit("downloads/unanet_invoice_payload.json not found")

    with open(payload_file, "r", encoding="utf-8") as f:
        return json.load(f)


def create_invoice(payload: dict):
    require_env("UNANET_BASE_URL", UNANET_BASE)
    require_env("UNANET_USERNAME", UNANET_USERNAME)
    require_env("UNANET_PASSWORD", UNANET_PASSWORD)

    # Based on your Swagger discovery
    url = f"{UNANET_BASE}/rest/vendor-invoices"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    data = {
        "invoiceNumber": payload["invoiceNumber"],
        "vendorId": payload["vendorId"],
        "invoiceDate": payload["invoiceDate"],
        "dueDate": payload["dueDate"],
        "amount": payload["amount"],
        "description": payload["description"]
    }

    print("\nUNANET_BASE:", UNANET_BASE)
    print("POST URL:", url)

    print("\nSending invoice to Unanet:")
    print(json.dumps(data, indent=2))

    r = requests.post(
        url,
        headers=headers,
        json=data,
        auth=(UNANET_USERNAME, UNANET_PASSWORD),
        timeout=60
    )

    print("\nStatus code:", r.status_code)
    print("Response content-type:", r.headers.get("Content-Type"))

    if r.status_code not in [200, 201]:
        print("\nUnanet error:")
        print(r.text[:5000])
        return None

    try:
        response = r.json()
    except Exception:
        print("\nSuccess status, but response is not JSON:")
        print(r.text[:5000])
        return None

    print("\nInvoice created in Unanet:")
    print(json.dumps(response, indent=2))
    return response


def main():
    payload = load_payload()
    response = create_invoice(payload)

    if response:
        print("\nSUCCESS: Invoice pushed to Unanet")


if __name__ == "__main__":
    main()