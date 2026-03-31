import os
import json
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BILL_USERNAME = os.getenv("BILL_USERNAME")
BILL_PASSWORD = os.getenv("BILL_PASSWORD")
BILL_ORG_ID = os.getenv("BILL_ORG_ID")
BILL_DEV_KEY = os.getenv("BILL_DEV_KEY")
BILL_API_BASE = os.getenv("BILL_API_BASE", "https://api.bill.com").rstrip("/")

DOWNLOAD_DIR = Path("downloads/bill_pdfs")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def require_env(name: str, value: str | None) -> str:
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def login() -> str:
    username = require_env("BILL_USERNAME", BILL_USERNAME)
    password = require_env("BILL_PASSWORD", BILL_PASSWORD)
    require_env("BILL_ORG_ID", BILL_ORG_ID)
    require_env("BILL_DEV_KEY", BILL_DEV_KEY)

    url = f"{BILL_API_BASE}/api/v2/Login.json"
    payload = {
        "userName": username,
        "password": password,
        "orgId": BILL_ORG_ID,
        "devKey": BILL_DEV_KEY,
    }

    r = requests.post(url, data=payload, timeout=30)
    r.raise_for_status()

    data = r.json()
    print("\nLogin response:")
    print(json.dumps(data, indent=2)[:2000])

    session_id = data.get("response_data", {}).get("sessionId") or data.get("sessionId")
    if not session_id:
        raise RuntimeError(
            f"Login succeeded but no sessionId found:\n{json.dumps(data, indent=2)}"
        )

    print("\nLogged in to BILL successfully.")
    print("Session ID acquired.")
    return session_id


def get_bill_document_info(session_id: str, bill_id: str) -> dict:
    url = f"{BILL_API_BASE}/api/v2/GetDocuments.json"

    headers = {
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
    }

    payload = {
        "devKey": BILL_DEV_KEY,
        "sessionId": session_id,
        "data": json.dumps({
            "id": bill_id,
            "start": 0,
            "max": 20
        }),
    }

    r = requests.post(url, headers=headers, data=payload, timeout=30)
    r.raise_for_status()

    data = r.json()
    print(f"\nGetDocuments response for bill {bill_id}:")
    print(json.dumps(data, indent=2)[:5000])

    if data.get("response_status") == 1:
        response_data = data.get("response_data", {})
        error_code = response_data.get("error_code", "UNKNOWN")
        error_message = response_data.get("error_message", "Unknown BILL API error")
        raise RuntimeError(f"{error_code}: {error_message}")

    return data


def sanitize_filename(name: str) -> str:
    name = name.strip().replace("\\", "_").replace("/", "_")
    return re.sub(r'[<>:"|?*]+', "_", name)


def extract_documents_info(doc_response: dict) -> list[dict]:
    """
    Returns a list of document info dictionaries:
    [
        {
            "document_id": "...",
            "file_name": "...",
            "download_url": "..."
        },
        ...
    ]
    """
    response_data = doc_response.get("response_data", {})
    documents = response_data.get("documents", [])

    if not documents:
        return []

    results = []
    for doc in documents:
        document_id = doc.get("id")
        file_name = doc.get("fileName") or "bill_attachment.pdf"

        if not document_id:
            continue

        results.append({
            "document_id": document_id,
            "file_name": file_name,
            "download_url": f"{BILL_API_BASE}/DownloadBillDocumentServlet"
        })

    return results


def download_bill_document(
    session_id: str,
    bill_id: str,
    document_id: str,
    file_name: str,
    download_url: str
) -> Path:
    safe_name = sanitize_filename(file_name)

    # make filename unique by prefixing bill_id + document_id
    unique_name = f"{bill_id}_{document_id}_{safe_name}"
    out_path = DOWNLOAD_DIR / unique_name

    headers = {
        "sessionId": session_id,
    }

    params = {
        "entityId": bill_id,
        "id": document_id,
    }

    with requests.get(download_url, headers=headers, params=params, stream=True, timeout=60) as r:
        r.raise_for_status()

        content_type = r.headers.get("Content-Type", "")
        print(f"\nDownload content-type for bill {bill_id}, doc {document_id}: {content_type}")

        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    return out_path


def download_documents_for_bill(session_id: str, bill_id: str) -> tuple[int, int]:
    """
    Returns:
        (success_count, failure_count)
    """
    try:
        doc_info = get_bill_document_info(session_id, bill_id)
        documents = extract_documents_info(doc_info)

        if not documents:
            print(f"No documents found for bill {bill_id}")
            return 0, 0

        success = 0
        failed = 0

        print(f"Found {len(documents)} document(s) for bill {bill_id}")

        for idx, doc in enumerate(documents, start=1):
            try:
                print(f"\nDownloading document {idx}/{len(documents)} for bill {bill_id}")
                print(f"Document ID: {doc['document_id']}")
                print(f"File name: {doc['file_name']}")

                path = download_bill_document(
                    session_id=session_id,
                    bill_id=bill_id,
                    document_id=doc["document_id"],
                    file_name=doc["file_name"],
                    download_url=doc["download_url"]
                )
                print(f"Downloaded: {path}")
                success += 1

            except Exception as e:
                print(f"Failed document {doc.get('document_id')} for bill {bill_id}: {e}")
                failed += 1

        return success, failed

    except Exception as e:
        print(f"Failed for bill {bill_id}: {e}")
        return 0, 1


def load_bill_ids():
    bill_ids_file = Path("downloads/bill_ids_with_docs.txt")

    if not bill_ids_file.exists():
        raise SystemExit("downloads/bill_ids_with_docs.txt not found.")

    bill_ids = [
        line.strip()
        for line in bill_ids_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    print(f"Loaded {len(bill_ids)} bill IDs with documents")
    return bill_ids


def main():
    require_env("BILL_USERNAME", BILL_USERNAME)
    require_env("BILL_PASSWORD", BILL_PASSWORD)
    require_env("BILL_ORG_ID", BILL_ORG_ID)
    require_env("BILL_DEV_KEY", BILL_DEV_KEY)

    session_id = login()
    bill_ids = load_bill_ids()

    total_success = 0
    total_failed = 0

    # IMPORTANT: test first 10 bills only
    for i, bill_id in enumerate(bill_ids[:10], start=1):
        print(f"\n{'=' * 80}")
        print(f"Processing bill {i} / {len(bill_ids)} -> {bill_id}")
        print(f"{'=' * 80}")

        success, failed = download_documents_for_bill(session_id, bill_id)
        total_success += success
        total_failed += failed

    print(f"\nDone. Success: {total_success}, Failed: {total_failed}")


if __name__ == "__main__":
    main()