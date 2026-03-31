import json
from pathlib import Path

DOWNLOAD_DIR = Path("downloads")


def find_latest_bill():
    """
    Find the most recent bill json file in downloads folder.
    """
    bill_files = list(DOWNLOAD_DIR.glob("*_bill.json"))

    if not bill_files:
        raise SystemExit("No bill metadata found in downloads folder.")

    bill_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return bill_files[0]


def extract_invoice_data(bill_json_path):
    """
    Extract important invoice fields from Bill.com metadata
    """

    with open(bill_json_path, "r") as f:
        bill = json.load(f)

    invoice = {
        "invoiceNumber": bill.get("invoiceNumber"),
        "vendorId": bill.get("vendorId"),
        "amount": bill.get("amount"),
        "invoiceDate": bill.get("invoiceDate"),
        "dueDate": bill.get("dueDate"),
        "description": bill.get("description"),
        "billId": bill.get("id")
    }

    return invoice


def save_prepared_invoice(data):
    """
    Save formatted invoice data for Unanet
    """

    output_file = DOWNLOAD_DIR / "unanet_invoice_payload.json"

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print("\nPrepared Unanet invoice payload saved:")
    print(output_file)


def main():

    print("Searching for latest bill metadata...")

    bill_file = find_latest_bill()
    print("Using:", bill_file)

    invoice_data = extract_invoice_data(bill_file)

    print("\nExtracted invoice data:")
    print(json.dumps(invoice_data, indent=2))

    save_prepared_invoice(invoice_data)


if __name__ == "__main__":
    main()