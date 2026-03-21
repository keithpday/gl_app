"""Google Sheets access functions."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import gspread

from config import (
    BAND_MEMBERS_SHEET_NAME,
    CASH_ACCOUNT,
    CHART_ACCOUNT_COLUMN_NUMBER,
    CHART_OF_ACCOUNTS_SHEET_NAME,
    COMPLETED_GIGS_SHEET_NAME,
    DATE_FORMAT,
    FIRST_SEQ,
    JOURNAL_COLUMNS,
    JOURNAL_COLUMN_COUNT,
    JOURNAL_LAST_COLUMN,
    JOURNAL_SHEET_NAME,
    MAX_SCHEDULE_ROWS_TO_DISPLAY,
    PERFORMANCE_HISTORY_ID,
    PERFORMANCE_SCHEDULE_ID,
    RECURRING_SHEET_NAME,
    SALES_PERFORMANCES_ACCOUNT,
    SCHEDULE_SHEET_NAME,
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
            row[header_index["Comment"]] = line.comment or entry.comment
            rows_to_append.append(row)

        self._debug(
            f"Appending {len(rows_to_append)} row(s) to {JOURNAL_SHEET_NAME} "
            f"for Seq {entry.seq}"
        )

        old_row_count = self.journal_ws.row_count

        try:
            self.journal_ws.append_rows(
                rows_to_append,
                value_input_option="USER_ENTERED",
            )
        except Exception as exc:
            raise SheetsApiError(f"Unable to append journal entry: {exc}") from exc

        self._debug(f"Append complete for Seq {entry.seq}")

        # Set formulas for DaysOld (K) and Balance Remaining (L) columns
        new_row_count = self.journal_ws.row_count
        updates = []
        for i in range(old_row_count + 1, new_row_count + 1):
            days_old_formula = (
                f'=IF(OR(G{i}="INV", G{i}="PMT", G{i}="DEP", G{i}="CRN", G{i}="ADJ", G{i}="ACH"), '
                f'IF(ISBLANK(H{i}), "", '
                f'(DATE(2023,11,7)+(VALUE(IFERROR(REGEXEXTRACT(H{i}, "\\d+"),0))-1) - TODAY()) * -1 ), "")'
            )
            balance_formula = (
                f'=SUMIFS($E:$E,$H:$H,$H{i},$G:$G,"INV") - '
                f'(SUMIFS($F:$F,$H:$H,$H{i},$G:$G,"PMT") + '
                f'SUMIFS($F:$F,$H:$H,$H{i},$G:$G,"DEP") + '
                f'SUMIFS($F:$F,$H:$H,$H{i},$G:$G,"CRN") + '
                f'SUMIFS($F:$F,$H:$H,$H{i},$G:$G,"ADJ") + '
                f'SUMIFS($F:$F,$H:$H,$H{i},$G:$G,"ACH"))'
            )
            updates.append({'range': f'K{i}', 'values': [[days_old_formula]]})
            updates.append({'range': f'L{i}', 'values': [[balance_formula]]})

        if updates:
            try:
                self.journal_ws.batch_update(updates)
                self._debug(f"Updated formulas for {len(updates)//2} new rows")
            except Exception as exc:
                raise SheetsApiError(f"Unable to update formulas: {exc}") from exc

    def get_performance_schedule(self) -> list[dict[str, str]]:
        """Get the first MAX_SCHEDULE_ROWS_TO_DISPLAY rows from the performance schedule."""
        try:
            # Open the performance schedule spreadsheet
            schedule_gc = gspread.service_account(self.credentials_path)
            schedule_spreadsheet = schedule_gc.open_by_key(PERFORMANCE_SCHEDULE_ID)
            schedule_ws = schedule_spreadsheet.worksheet(SCHEDULE_SHEET_NAME)
            self._debug(f"Opened performance schedule worksheet: {SCHEDULE_SHEET_NAME}")
            
            # Get all rows but limit to MAX_SCHEDULE_ROWS_TO_DISPLAY
            values = schedule_ws.get("A1:S")  # Up to column S (#in Bnd)
            if not values:
                self._debug("No performance schedule data found")
                return []
                
            headers = values[0]
            data_rows = values[1:MAX_SCHEDULE_ROWS_TO_DISPLAY + 1]  # +1 for header
            
            rows: list[dict[str, str]] = []
            for row in data_rows:
                padded = row + [""] * (len(headers) - len(row))
                rows.append({headers[idx]: padded[idx] for idx in range(len(headers))})
            
            self._debug(f"Loaded {len(rows)} performance schedule row(s)")
            return rows
            
        except Exception as exc:
            raise SheetsApiError(f"Unable to read performance schedule: {exc}") from exc

    def get_band_members(self) -> dict[str, dict[str, str]]:
        """Get band members data keyed by Alias."""
        try:
            # Open the performance schedule spreadsheet
            schedule_gc = gspread.service_account(self.credentials_path)
            schedule_spreadsheet = schedule_gc.open_by_key(PERFORMANCE_SCHEDULE_ID)
            band_ws = schedule_spreadsheet.worksheet(BAND_MEMBERS_SHEET_NAME)
            self._debug(f"Opened band members worksheet: {BAND_MEMBERS_SHEET_NAME}")
            
            values = band_ws.get("A1:K")  # Up to column K (Alias)
            if not values:
                self._debug("No band members data found")
                return {}
                
            headers = values[0]
            data_rows = values[1:]
            
            members: dict[str, dict[str, str]] = {}
            for row in data_rows:
                if len(row) >= len(headers):
                    member_data = {headers[idx]: row[idx] for idx in range(len(headers))}
                    alias = member_data.get("Alias", "").strip()
                    if alias:
                        members[alias] = member_data
            
            self._debug(f"Loaded {len(members)} band member(s)")
            return members
            
        except Exception as exc:
            raise SheetsApiError(f"Unable to read band members: {exc}") from exc

    def move_completed_gig_to_history(self, gig_row: dict[str, str]) -> None:
        """Move a completed gig row to the history spreadsheet."""
        try:
            # Open history spreadsheet
            history_gc = gspread.service_account(self.credentials_path)
            history_spreadsheet = history_gc.open_by_key(PERFORMANCE_HISTORY_ID)
            history_ws = history_spreadsheet.worksheet(COMPLETED_GIGS_SHEET_NAME)
            self._debug(f"Opened completed gigs worksheet: {COMPLETED_GIGS_SHEET_NAME}")
            
            # Convert dict back to row format
            headers = list(gig_row.keys())
            row_values = [gig_row[header] for header in headers]
            
            # Append to history
            history_ws.append_row(row_values, value_input_option="USER_ENTERED")
            self._debug("Appended gig to history")
            
        except Exception as exc:
            raise SheetsApiError(f"Unable to move gig to history: {exc}") from exc

    def move_completed_gigs_before_date(self, cutoff_date: date) -> int:
        """Copy rows from CurrentYrSched to CompletedGigs where Date <= cutoff_date, then delete them from schedule."""
        try:
            schedule_gc = gspread.service_account(self.credentials_path)
            schedule_spreadsheet = schedule_gc.open_by_key(PERFORMANCE_SCHEDULE_ID)
            schedule_ws = schedule_spreadsheet.worksheet(SCHEDULE_SHEET_NAME)
            self._debug(f"Opened schedule worksheet: {SCHEDULE_SHEET_NAME}")

            history_gc = gspread.service_account(self.credentials_path)
            history_spreadsheet = history_gc.open_by_key(PERFORMANCE_HISTORY_ID)
            history_ws = history_spreadsheet.worksheet(COMPLETED_GIGS_SHEET_NAME)
            self._debug(f"Opened completed gigs worksheet: {COMPLETED_GIGS_SHEET_NAME}")

            values = schedule_ws.get("A1:S")
            if not values or len(values) < 2:
                self._debug("No schedule rows available in CurrentYrSched")
                return 0

            headers = values[0]
            data_rows = values[1:]

            # Determine date column index
            if "Date" in headers:
                date_idx = headers.index("Date")
            else:
                raise SheetsApiError("CurrentYrSched is missing a 'Date' header in A1:S")

            rows_to_move = []
            rows_to_delete_indices = []

            for idx, row in enumerate(data_rows, start=2):
                # Ensure first 19 columns are present
                row_padded = (row + [""] * 19)[:19]
                raw_date = row_padded[date_idx]
                row_date = _parse_date_strict(raw_date)

                if row_date is None:
                    self._debug(f"Skipping unmatched date in row {idx}: {raw_date!r}")
                    continue

                if row_date <= cutoff_date:
                    rows_to_move.append(row_padded)
                    rows_to_delete_indices.append(idx)

            if not rows_to_move:
                self._debug(f"No rows found with Date <= {cutoff_date}")
                return 0

            # Append rows to history in bulk
            history_ws.append_rows(rows_to_move, value_input_option="USER_ENTERED")
            self._debug(f"Appended {len(rows_to_move)} completed gig(s) to history")

            # Delete rows starting from the bottom to avoid index shift
            for row_index in reversed(rows_to_delete_indices):
                schedule_ws.delete_rows(row_index)
            self._debug(f"Deleted {len(rows_to_delete_indices)} row(s) from schedule")

            return len(rows_to_move)

        except Exception as exc:
            raise SheetsApiError(f"Unable to move completed gigs by date: {exc}") from exc

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


def _parse_date_strict(value: object) -> date | None:
    text = str(value).strip()
    if not text:
        return None

    # Try common date formats and known datetime representations
    formats = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%m/%d/%Y %H:%M:%S", "%m/%d/%y", "%m/%d/%y %H:%M:%S"]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    # Try ISO parsing as a last resort
    try:
        dt = datetime.fromisoformat(text)
        return dt.date()
    except ValueError:
        return None

