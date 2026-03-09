from config import DEFAULT_CREDENTIALS_FILE
from sheets_api import SheetsClient, SheetsApiError
from config import DEFAULT_CREDENTIALS_FILE

print("Using credentials file:", DEFAULT_CREDENTIALS_FILE)

def main():
    try:
        client = SheetsClient(DEFAULT_CREDENTIALS_FILE)
        print("Connected to spreadsheet.")
        print("Next Seq:", client.get_next_seq())

        accounts = client.get_valid_accounts()
        print(f"Loaded {len(accounts)} accounts.")
        print("First 10 accounts:")
        for acct in accounts[:10]:
            print("  ", acct)

    except SheetsApiError as exc:
        print("SheetsApiError:", exc)
    except Exception as exc:
        print("Unexpected error:", exc)

if __name__ == "__main__":
    main()
