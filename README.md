# Mixed Nuts GL Journal Entry App

This is a terminal-based starter framework for posting journal entries into your Google Sheets general ledger.

## Current entry types

1. Mobile Deposit to Checking
2. Auto Deposit to Checking
3. Transfer Between Checking and Savings
4. Post Recurring Entry
5. Post Performance Entry

## Design goal

The code separates:

- **business logic** (`journal_logic.py`)
- **Google Sheets access** (`sheets_api.py`)
- **CLI prompts** (`prompts.py`)
- **entry workflows** (`entry_handlers.py`)

That makes it much easier to move to a GUI later.

## Files

- `main.py` - main menu and posting loop
- `config.py` - spreadsheet IDs, sheet names, account constants, sequence rules
- `models.py` - journal entry dataclasses
- `journal_logic.py` - validation and entry construction
- `prompts.py` - terminal prompts
- `entry_handlers.py` - per-entry workflow handlers
- `sheets_api.py` - gspread integration

## Requirements

```bash
pip install gspread google-auth
```

## Credentials

Update `DEFAULT_CREDENTIALS_PATH` in `config.py`, or pass the path on the command line:

```bash
python3 main.py /path/to/your/service-account.json
```

## Run

```bash
cd /path/to/Mixed_Nuts_gl_app
python3 main.py
```

## Notes

- `Seq` increments by **100**.
- All lines in the same journal entry use the same `Seq`.
- The program reads valid accounts from the `ChAccts` tab, column **G**.
- The program appends rows to `GenEnt` with no blank rows.
- For Mobile Deposit, the debit side is fixed to **Checking - 0520** and you choose the credit account.

## Good next additions

- ACH deposit entry type
- band performance entry type
- dropdown-like account picker in CLI
- copy formulas into computed columns if needed
- log file / audit trail
