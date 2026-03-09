"""Google Sheets access functions."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import gspread

from config import (
    CHART_ACCOUNT_COLUMN_NUMBER,
    CHART_OF_ACCOUNTS_SHEET_NAME,
    DATE_FORMAT,
    FIRST_SEQ,
    JOURNAL_COLUMNS,
    JOURNAL_COLUMN_COUNT,
    JOURNAL_LAST_COLUMN,
    JOURNAL_SHEET_NAME,
    RECURRING_SHEET_NAME,
    SEQ_INCREMENT,
    SPREADSHEET_ID,
)
from models import JournalEntry, JournalLine, OpenInvoice


class SheetsApiError(Exception):
    """Raised for Google Sheets problems."""


class SheetsClient:
    def __init__(self, credentials_path: str, debug: bool = False):
        self.debug = debug
        self.credentials_path = credentials_path

        try:
            self._debug(f"Authorizing gspread with credentials file: {credentials_path}")
            self.gc = gspread.service_account(filename=credentials_path)

            self._debug(f"Opening spreadsheet by key: {SPREADSHEET_ID}")
            self.spreadsheet = self.gc.open_by_key(SPREADSHEET_ID)
            self._debug(f"Opened spreadsheet: {self.spreadsheet.title}")

            self.journal_ws = self.spreadsheet.worksheet(JOURNAL_SHEET_NAME)
            self._debug(f"Opened journal worksheet: {JOURNAL_SHEET_NAME}")

            self.chart_ws = self.spreadsheet.worksheet(CHART_OF_ACCOUNTS_SHEET_NAME)
            self._debug(f"Opened chart worksheet: {CHART_OF_ACCOUNTS_SHEET_NAME}")

            self.recurring_ws = self.spreadsheet.worksheet(RECURRING_SHEET_NAME)
            self._debug(f"Opened recurring worksheet: {RECURRING_SHEET_NAME}")

            self._journal_headers = self.journal_ws.get(f"A1:{JOURNAL_LAST_COLUMN}1")[0]
            self._debug(f"Loaded journal headers A1:{JOURNAL_LAST_COLUMN}1: {self._journal_headers}")

            self._recurring_headers = self.recurring_ws.get(f"A1:{JOURNAL_LAST_COLUMN}1")[0]
            self._debug(f"Loaded recurring headers A1:{JOURNAL_LAST_COLUMN}1: {self._recurring_headers}")

        except Exception as exc:
            raise SheetsApiError(f"Unable to connect to Google Sheets: {exc}") from exc

    def _debug(self, message: str) -> None:
        if self.debug:
            print(f"[DEBUG:sheets] {message}")

    def get_valid_accounts(self) -> list[str]:
        try:
            self._debug(
                f"Reading chart of accounts column {CHART_ACCOUNT_COLUMN_NUMBER} "
                f"from worksheet {CHART_OF_ACCOUNTS_SHEET_NAME}"
            )
            column_values = self.chart_ws.col_values(CHART_ACCOUNT_COLUMN_NUMBER)
        except Exception as exc:
            raise SheetsApiError(f"Unable to read chart of accounts: {exc}") from exc

        accounts: list[str] = []
        for idx, value in enumerate(column_values, start=1):
            cleaned = value.strip()
            if idx == 1 and cleaned.lower() == "individual accounts":
                continue
            if cleaned:
                accounts.append(cleaned)

        unique_accounts = sorted(set(accounts))
        self._debug(f"Loaded {len(unique_accounts)} unique valid accounts")
        return unique_accounts

    def get_next_seq(self) -> int:
        try:
            self._debug("Reading Seq column from GenEnt")
            seq_values = self.journal_ws.col_values(1)[1:]
        except Exception as exc:
            raise SheetsApiError(f"Unable to read Seq column: {exc}") from exc

        max_seq = 0
        for raw in seq_values:
            text = str(raw).strip()
            if not text:
                continue
            try:
                max_seq = max(max_seq, int(float(text)))
            except ValueError:
                continue

        next_seq = FIRST_SEQ if max_seq == 0 else max_seq + SEQ_INCREMENT
        self._debug(f"Computed next Seq: {next_seq} (max existing Seq: {max_seq})")
        return next_seq

    def get_open_invoices_for_account(self, account: str) -> list[OpenInvoice]:
        try:
            self._debug(f"Reading open invoices for account: {account}")
            values = self.journal_ws.get(f"A1:{JOURNAL_LAST_COLUMN}")
        except Exception as exc:
            raise SheetsApiError(f"Unable to read GenEnt rows: {exc}") from exc

        if not values:
            self._debug("No values found in GenEnt A:M")
            return []

        headers = values[0]
        data_rows = values[1:]

        header_index = {name: idx for idx, name in enumerate(headers)}
        required = ["Account", "DocType", "DocNbr", "Balance Remaining"]
        missing = [name for name in required if name not in header_index]
        if missing:
            raise SheetsApiError(f"GenEnt is missing expected headers in A:M: {missing}")

        invoices: list[OpenInvoice] = []
        for row in data_rows:
            padded = row + [""] * (len(headers) - len(row))

            row_account = str(padded[header_index["Account"]]).strip()
            doc_type = str(padded[header_index["DocType"]]).strip().upper()
            doc_nbr = str(padded[header_index["DocNbr"]]).strip()
            balance_raw = padded[header_index["Balance Remaining"]]

            if row_account != account:
                continue
            if doc_type != "INV":
                continue
            if not doc_nbr:
                continue

            balance = _parse_decimal(balance_raw)
            if balance == Decimal("0.00"):
                continue

            invoices.append(
                OpenInvoice(
                    account=row_account,
                    doc_nbr=doc_nbr,
                    balance_remaining=balance,
                )
            )

        invoices.sort(key=lambda inv: (inv.doc_nbr, inv.balance_remaining))
        self._debug(f"Found {len(invoices)} open invoices for account {account}")
        return invoices

    def display_recurring_entries(self) -> None:
        try:
            self._debug("Reading RecEnt rows A:I for display")
            values = self.recurring_ws.get("A1:I")
        except Exception as exc:
            raise SheetsApiError(f"Unable to read RecEnt rows: {exc}") from exc

        if not values:
            print("No recurring entries found.")
            self._debug("No recurring entries found in RecEnt")
            return

        rows = values[1:]

        print()
        print("Recurring Entries (A:I)")
        print("-" * 120)
        print(
            f"{'Seq':<6} {'Date':<12} {'Description':<20} {'Account':<34} "
            f"{'Debit':>10} {'Credit':>10} {'DocType':<8} {'DocNbr':<12} {'ExtDoc':<12}"
        )
        print("-" * 120)

        count = 0
        for row in rows:
            padded = row + [""] * (9 - len(row))
            print(
                f"{padded[0]:<6} {padded[1]:<12} {padded[2]:<20} {padded[3]:<34} "
                f"{padded[4]:>10} {padded[5]:>10} {padded[6]:<8} {padded[7]:<12} {padded[8]:<12}"
            )
            count += 1

        print("-" * 120)
        self._debug(f"Displayed {count} recurring rows from RecEnt")

    def get_recurring_entry_by_seq(self, seq: int) -> JournalEntry:
        rows = self._get_sheet_rows(self.recurring_ws)
        self._debug(f"Searching RecEnt for Seq {seq}")

        matching = [row for row in rows if _parse_int(row.get("Seq", "")) == seq]
        if not matching:
            raise SheetsApiError(f"No recurring entry found for Seq {seq} in RecEnt.")

        first = matching[0]
        entry = JournalEntry(
            entry_date=_parse_date(first.get("Date", "")),
            description=str(first.get("Description", "")).strip(),
            comment=str(first.get("Comment", "")).strip(),
            seq=None,
            lines=[],
        )

        for row in matching:
            entry.lines.append(
                JournalLine(
                    account=str(row.get("Account", "")).strip(),
                    debit=_parse_decimal(row.get("Debit", "")),
                    credit=_parse_decimal(row.get("Credit", "")),
                    doc_type=str(row.get("DocType", "")).strip(),
                    doc_nbr=str(row.get("DocNbr", "")).strip(),
                    ext_doc=str(row.get("ExtDoc", "")).strip(),
                )
            )

        self._debug(f"Loaded recurring entry Seq {seq} with {len(entry.lines)} lines")
        return entry

    def append_entry(self, entry: JournalEntry) -> None:
        if entry.seq is None:
            raise SheetsApiError("Entry must have a seq before posting.")

        header_index = {name: idx for idx, name in enumerate(self._journal_headers)}
        missing = [name for name in JOURNAL_COLUMNS if name not in header_index]
        if missing:
            raise SheetsApiError(f"Journal sheet is missing expected headers in A:M: {missing}")

        width = JOURNAL_COLUMN_COUNT
        rows_to_append: list[list[str]] = []

        for line in entry.lines:
            row = ["" for _ in range(width)]
            row[header_index["Seq"]] = str(entry.seq)
            row[header_index["Date"]] = entry.entry_date.strftime(DATE_FORMAT)
            row[header_index["Description"]] = entry.description
            row[header_index["Account"]] = line.account
            row[header_index["Debit"]] = _decimal_to_sheet_string(line.debit)
            row[header_index["Credit"]] = _decimal_to_sheet_string(line.credit)
            row[header_index["DocType"]] = line.doc_type
            row[header_index["DocNbr"]] = line.doc_nbr
            row[header_index["ExtDoc"]] = line.ext_doc
            row[header_index["Comment"]] = entry.comment
            rows_to_append.append(row)

        self._debug(
            f"Appending {len(rows_to_append)} row(s) to {JOURNAL_SHEET_NAME} "
            f"for Seq {entry.seq}"
        )

        try:
            self.journal_ws.append_rows(
                rows_to_append,
                value_input_option="USER_ENTERED",
            )
        except Exception as exc:
            raise SheetsApiError(f"Unable to append journal entry: {exc}") from exc

        self._debug(f"Append complete for Seq {entry.seq}")

    def _get_sheet_rows(self, worksheet: gspread.Worksheet) -> list[dict[str, str]]:
        try:
            self._debug(f"Reading worksheet rows A:{JOURNAL_LAST_COLUMN} from {worksheet.title}")
            values = worksheet.get(f"A1:{JOURNAL_LAST_COLUMN}")
        except Exception as exc:
            raise SheetsApiError(f"Unable to read worksheet rows: {exc}") from exc

        if not values:
            self._debug(f"No values found in worksheet {worksheet.title}")
            return []

        headers = values[0]
        data_rows = values[1:]

        rows: list[dict[str, str]] = []
        for row in data_rows:
            padded = row + [""] * (len(headers) - len(row))
            rows.append({headers[idx]: padded[idx] for idx in range(len(headers))})

        self._debug(f"Loaded {len(rows)} data row(s) from worksheet {worksheet.title}")
        return rows


def _decimal_to_sheet_string(value: Decimal) -> str:
    if value == Decimal("0.00"):
        return ""
    return f"{value:.2f}"


def _parse_decimal(value: object) -> Decimal:
    text = str(value).strip().replace(",", "")
    if not text:
        return Decimal("0.00")
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0.00")


def _parse_int(value: object) -> int | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_date(value: object) -> date:
    text = str(value).strip()
    if not text:
        return date.today()

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    return date.today()
