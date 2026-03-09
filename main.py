#!/usr/bin/env python3
"""CLI entry point for the Mixed Nuts GL journal-entry system."""

from __future__ import annotations

import sys
from pathlib import Path

from config import DEFAULT_CREDENTIALS_FILE
from entry_handlers import (
    handle_auto_deposit_entry,
    handle_mobile_deposit_entry,
    handle_performance_entry,
    handle_recurring_entry,
    handle_transfer_entry,
)
from journal_logic import JournalLogicError
from models import JournalEntry
from prompts import prompt_menu_choice, prompt_yes_no
from sheets_api import SheetsApiError, SheetsClient


def debug_print(debug: bool, message: str) -> None:
    if debug:
        print(f"[DEBUG] {message}")


def print_entry_preview(entry: JournalEntry) -> None:
    print("\nEntry Preview")
    print(f"Seq:         {entry.seq}")
    print(f"Date:        {entry.entry_date}")
    print(f"Description: {entry.description}")
    print(f"Comment:     {entry.comment}")
    print()

    print(
        f"{'Account':34} {'Debit':>10} {'Credit':>10} "
        f"{'DocType':>8} {'DocNbr':>12} {'ExtDoc':>14} {'Comment':<20}"
    )
    print("-" * 116)
    for line in entry.lines:
        debit = f"{line.debit:.2f}" if line.debit else ""
        credit = f"{line.credit:.2f}" if line.credit else ""
        comment = line.comment or entry.comment
        print(
            f"{line.account:34} {debit:>10} {credit:>10} "
            f"{line.doc_type:>8} {line.doc_nbr:>12} {line.ext_doc:>14} {comment:<20}"
        )
    print("-" * 116)
    print(
        f"{'Totals':34} "
        f"{entry.total_debits():>10.2f} "
        f"{entry.total_credits():>10.2f}"
        f"{'':<8} {'':<12} {'':<14} {'':<20}"
    )


def parse_args() -> tuple[str, bool]:
    debug = False
    creds_file = DEFAULT_CREDENTIALS_FILE

    for arg in sys.argv[1:]:
        if arg == "--debug":
            debug = True
        else:
            creds_file = arg

    return creds_file, debug


def main() -> int:
    creds_file, debug = parse_args()

    debug_print(debug, f"Credentials file resolved to: {creds_file}")
    debug_print(debug, f"Debug mode enabled: {debug}")

    if not Path(creds_file).exists():
        print(f"Credentials file not found: {creds_file}")
        print("Pass the path on the command line or update DEFAULT_CREDENTIALS_FILE in config.py")
        return 1

    try:
        print("Starting General Ledger Journal Entry System...")
        print("Connecting to Google Sheets...")
        client = SheetsClient(creds_file, debug=debug)
        valid_accounts = client.get_valid_accounts()
        debug_print(debug, f"Loaded {len(valid_accounts)} valid accounts from ChAccts")
        print("Ready.\n")
    except Exception as exc:
        print(f"Startup error: {exc}")
        return 1

    while True:
        choice = prompt_menu_choice()
        debug_print(debug, f"Menu choice entered: {choice}")

        if choice == "1":
            builder = lambda: handle_mobile_deposit_entry(client, valid_accounts, debug=debug)
            debug_print(debug, "Selected workflow: Mobile Deposit to Checking")
        elif choice == "2":
            builder = lambda: handle_auto_deposit_entry(client, valid_accounts, debug=debug)
            debug_print(debug, "Selected workflow: Auto Deposit to Checking")
        elif choice == "3":
            builder = lambda: handle_transfer_entry(debug=debug)
            debug_print(debug, "Selected workflow: Transfer Between Checking and Savings")
        elif choice == "4":
            builder = lambda: handle_recurring_entry(client, debug=debug)
            debug_print(debug, "Selected workflow: Post Recurring Entry")
        elif choice == "5":
            builder = lambda: handle_performance_entry(client, debug=debug)
            debug_print(debug, "Selected workflow: Post Performance Entry")
        elif choice == "6":
            debug_print(debug, "User selected Exit")
            print("Goodbye.")
            return 0
        else:
            print("Please choose 1, 2, 3, 4, 5, or 6.")
            continue

        try:
            entry = builder()
            debug_print(debug, "Entry built successfully")
            debug_print(debug, f"Entry description: {entry.description}")
            debug_print(debug, f"Entry line count: {len(entry.lines)}")

            entry.seq = client.get_next_seq()
            debug_print(debug, f"Assigned new Seq: {entry.seq}")

            print_entry_preview(entry)

            if prompt_yes_no("Post this entry", default_yes=False):
                debug_print(debug, f"Posting entry Seq {entry.seq}")
                client.append_entry(entry)
                print(f"Entry {entry.seq} posted successfully.")
                debug_print(debug, f"Entry {entry.seq} posted successfully")
            else:
                debug_print(debug, "User declined posting")
                print("Entry not posted.")

        except (JournalLogicError, SheetsApiError, ValueError) as exc:
            print(f"Error: {exc}")
            debug_print(debug, f"Handled exception type: {type(exc).__name__}")
        except KeyboardInterrupt:
            print("\nCancelled.")
            debug_print(debug, "KeyboardInterrupt caught during workflow")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
