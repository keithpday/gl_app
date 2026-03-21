"""CLI-only prompts. Replace this file later if you build a GUI."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from config import DISPLAY_DATE_FORMAT
from journal_logic import JournalLogicError, money
from models import OpenInvoice, RecurringEntrySummary

def prompt_menu_choice() -> str:
    print("\nGeneral Ledger Journal Entry System")
    print("1. Mobile Deposit to Checking")
    print("2. Auto Deposit to Checking")
    print("3. Transfer Between Checking and Savings")
    print("4. Post Recurring Entry")
    print("5. Post Performance Entry")
    print("6. Move Completed Gigs to History by Date")
    print("7. Exit")
    return input("Select option: ").strip()


def prompt_seq_number(label: str = "Enter Seq to copy") -> int:
    while True:
        raw = input(f"{label}: ").strip()
        try:
            return int(raw)
        except ValueError:
            print("Please enter a valid sequence number.")

def prompt_date(default_date: date | None = None) -> date:
    default_date = default_date or date.today()
    while True:
        raw = input(f"Date [{default_date.strftime(DISPLAY_DATE_FORMAT)}]: ").strip()
        if not raw:
            return default_date
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                pass
        print("Invalid date. Use YYYY-MM-DD or MM/DD/YYYY.")


def prompt_amount() -> Decimal:
    while True:
        raw = input("Amount: ").strip().replace(",", "")
        try:
            return money(raw)
        except (JournalLogicError, ArithmeticError, ValueError) as exc:
            print(f"Invalid amount: {exc}")


def prompt_amount_with_default(label: str, default_amount: Decimal) -> Decimal:
    while True:
        raw = input(f"{label} [{default_amount:.2f}]: ").strip().replace(",", "")
        if not raw:
            return default_amount
        try:
            return money(raw)
        except (JournalLogicError, ArithmeticError, ValueError) as exc:
            print(f"Invalid amount: {exc}")


def prompt_text(label: str, default: str = "") -> str:
    if default:
        raw = input(f"{label} [{default}]: ").strip()
        return raw or default
    return input(f"{label}: ").strip()


def prompt_yes_no(label: str, default_yes: bool = True) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    while True:
        raw = input(f"{label} {suffix}: ").strip().lower()
        if not raw:
            return default_yes
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Please enter Y or N.")


def prompt_account(valid_accounts: list[str], label: str = "Credit account") -> str:
    while True:
        raw = input(f"{label}: ").strip()
        if raw in valid_accounts:
            return raw
        print("That account was not found in ChAccts column G.")
        matches = [acct for acct in valid_accounts if raw.lower() in acct.lower()][:10]
        if matches:
            print("Possible matches:")
            for acct in matches:
                print(f"  - {acct}")


def prompt_account_from_list(accounts: list[str], label: str = "Select account") -> str:
    if not accounts:
        raise ValueError("No accounts available for selection.")

    print(label)
    for idx, acct in enumerate(accounts, start=1):
        print(f"{idx}. {acct}")

    while True:
        raw = input("Choice: ").strip()
        try:
            choice = int(raw)
            if 1 <= choice <= len(accounts):
                return accounts[choice - 1]
        except ValueError:
            pass
        print(f"Please enter a number from 1 to {len(accounts)}.")


def prompt_account_by_prefix(
    valid_accounts: list[str],
    prefix: str,
    label: str = "Select account",
) -> str:
    matches = sorted(
        acct for acct in valid_accounts
        if acct.strip().lower().startswith(prefix.lower())
    )

    if not matches:
        raise ValueError(f'No accounts starting with "{prefix}" were found.')

    print(label)
    for idx, acct in enumerate(matches, start=1):
        print(f"{idx}. {acct}")

    while True:
        raw = input("Choice: ").strip()
        try:
            choice = int(raw)
            if 1 <= choice <= len(matches):
                return matches[choice - 1]
        except ValueError:
            pass
        print(f"Please enter a number from 1 to {len(matches)}.")


def prompt_check_number() -> str:
    while True:
        raw = input("Check number: ").strip().upper()
        if not raw:
            print("Check number cannot be blank.")
            continue
        if raw.startswith("CK#"):
            return raw
        return f"CK#{raw}"

def prompt_transaction_number() -> str:
    while True:
        raw = input("Transaction number: ").strip().upper()
        if not raw:
            print("Transaction number cannot be blank.")
            continue
        if raw.startswith("TR#"):
            return raw
        return f"TR#{raw}"

def prompt_open_invoice_or_manual(invoices: list[OpenInvoice]) -> str:
    if not invoices:
        print("No outstanding invoices found for this account.")
        return prompt_text("Invoice number")

    print("Select outstanding invoice")
    for idx, invoice in enumerate(invoices, start=1):
        print(
            f"{idx}. {invoice.account} | "
            f"DocNbr {invoice.doc_nbr} | "
            f"Balance {invoice.balance_remaining:.2f}"
        )
    manual_choice = len(invoices) + 1
    print(f"{manual_choice}. Enter invoice number manually")

    while True:
        raw = input("Choice: ").strip()
        try:
            choice = int(raw)
            if 1 <= choice <= len(invoices):
                return invoices[choice - 1].doc_nbr
            if choice == manual_choice:
                return prompt_text("Invoice number")
        except ValueError:
            pass
        print(f"Please enter a number from 1 to {manual_choice}.")


def prompt_recurring_entry_selection(
    summaries: list[RecurringEntrySummary],
) -> RecurringEntrySummary:
    if not summaries:
        raise ValueError("No recurring entries were found in RecEnt.")

    print("Select recurring entry")
    for idx, summary in enumerate(summaries, start=1):
        print(
            f"{idx}. Seq {summary.seq} | "
            f"{summary.description} | "
            f"Amount {summary.default_amount:.2f} | "
            f"Lines {summary.line_count}"
        )

    while True:
        raw = input("Choice: ").strip()
        try:
            choice = int(raw)
            if 1 <= choice <= len(summaries):
                return summaries[choice - 1]
        except ValueError:
            pass
        print(f"Please enter a number from 1 to {len(summaries)}.")
