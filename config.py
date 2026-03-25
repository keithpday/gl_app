"""Configuration for the Mixed Nuts general-ledger journal entry app."""

from pathlib import Path
import os

# Program / environment
PROGRAM_NAME = Path(__file__).stem

# Google credentials
DEFAULT_CREDENTIALS_FILE = os.environ.get(
    "GOOGLE_OAUTH_CLIENT",
    "/home/keith/PythonProjects/projects/Mixed_Nuts/config/gl-app-credentials.json",
)

# Google Sheets document
SPREADSHEET_ID = "1q9chtQNZnO5QcDBaYTjnV0sITxo7zAvTHfLT7MkZybs"
SPREADSHEET_NAME = "Current Quarter Booking and General Ledger"
JOURNAL_SHEET_NAME = "GenEnt"
CHART_OF_ACCOUNTS_SHEET_NAME = "ChAccts"
RECURRING_SHEET_NAME = "RecEnt"

# Performance tracking sheets
PERFORMANCE_SCHEDULE_ID = "1WS4-Y2M7qA0bqMhluvWOg3GiUyScBSY3ZIBPoNS7Tao"
PERFORMANCE_HISTORY_ID = "14c2cdCh0srxI40RGQomNPpXXWCT5IV8rcqVqw92N03U"
SCHEDULE_SHEET_NAME = "CurrentYrSched"
BAND_MEMBERS_SHEET_NAME = "BandMembers"
COMPLETED_GIGS_SHEET_NAME = "CompletedGigs"

# Performance constants
MAX_SCHEDULE_ROWS_TO_DISPLAY = 8

# Journal table boundaries (ignore anything to the right of M)
JOURNAL_LAST_COLUMN = "M"
JOURNAL_COLUMN_COUNT = 13

# Column names in GenEnt / RecEnt that this program writes to
JOURNAL_COLUMNS = [
    "Seq",
    "Date",
    "Description",
    "Account",
    "Debit",
    "Credit",
    "DocType",
    "DocNbr",
    "ExtDoc",
    "Comment",
]

# Known accounts
CHECKING_ACCOUNT = "Checking - 0520"
SAVINGS_ACCOUNT = "Savings - 0520"
CASH_ACCOUNT = "Cash"
CASH_IN_CD_CASE_ACCOUNT = "Cash in CD Case"
CASH_IN_DUO_GEAR_ACCOUNT = "Cash in Duo Gear"
CHECKING_ACCOUNT = "Checking - 0520"
VENMO_ACCOUNT = "Venmo"
SALES_PERFORMANCES_ACCOUNT = "Sales - Performances"
DONATIONS_ACCOUNT = "Donations"
CASH_PAYMENT_FEES_ACCOUNT = "Cash Payment Fees"

# CD master sheet
CD_MASTER_SPREADSHEET_ID = "1xfRniECqyI1liKrmnh3gD9zPobQfJLD8yHQF4QjiRzg"
CD_MASTER_SHEET_NAME = "CD_Master"

# Seq handling
SEQ_INCREMENT = 100
FIRST_SEQ = 100

# Chart of accounts layout
CHART_ACCOUNT_COLUMN_NUMBER = 7  # Column G
CHART_ACCOUNT_HEADER = "Individual Accounts"

# Date formatting used when writing to the sheet
DATE_FORMAT = "%m/%d/%Y"
DISPLAY_DATE_FORMAT = "%m/%d/%Y"
