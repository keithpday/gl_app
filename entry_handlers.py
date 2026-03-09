"""Workflow handlers that gather input and call the business logic."""

from __future__ import annotations

from decimal import Decimal

from models import JournalEntry
from journal_logic import (
    build_mobile_deposit_entry,
    build_transfer_entry,
    validate_entry,
)
from prompts import (
    prompt_account_by_prefix,
    prompt_amount,
    prompt_amount_with_default,
    prompt_check_number,
    prompt_date,
    prompt_open_invoice_or_manual,
    prompt_seq_number,
    prompt_text,
    prompt_transaction_number,
)
from sheets_api import SheetsClient


def debug_print(debug: bool, message: str) -> None:
    if debug:
        print(f"[DEBUG:handler] {message}")


def handle_transfer_entry(debug: bool = False) -> JournalEntry:
    print("\nTransfer Between Checking and Savings")
    entry_date = prompt_date()
    amount = prompt_amount()

    debug_print(debug, f"Transfer date entered: {entry_date}")
    debug_print(debug, f"Transfer amount entered: {amount}")

    print("1. Checking -> Savings")
    print("2. Savings -> Checking")
    direction_choice = prompt_text("Direction")

    direction = {
        "1": "checking_to_savings",
        "2": "savings_to_checking",
    }.get(direction_choice)
    if direction is None:
        raise ValueError("Direction must be 1 or 2.")

    comment = prompt_text("Comment")

    debug_print(debug, f"Transfer direction selected: {direction}")
    debug_print(debug, f"Transfer comment: {comment}")

    entry = build_transfer_entry(
        entry_date=entry_date,
        amount=amount,
        direction=direction,
        comment=comment,
    )

    debug_print(debug, f"Built transfer entry with {len(entry.lines)} lines")
    return entry


def handle_mobile_deposit_entry(
    client: SheetsClient,
    valid_accounts: list[str],
    debug: bool = False,
) -> JournalEntry:
    print("\nMobile Deposit to Checking")
    entry_date = prompt_date()
    amount = prompt_amount()
    description = prompt_text("Description", default="Mobile Deposit to Checking")

    debug_print(debug, f"Mobile deposit date entered: {entry_date}")
    debug_print(debug, f"Mobile deposit amount entered: {amount}")
    debug_print(debug, f"Mobile deposit description: {description}")

    credit_account = prompt_account_by_prefix(
        valid_accounts,
        prefix="Rcvbls",
        label="Select receivables account",
    )
    debug_print(debug, f"Mobile deposit receivables account selected: {credit_account}")

    open_invoices = client.get_open_invoices_for_account(credit_account)
    debug_print(debug, f"Open invoices found: {len(open_invoices)}")

    receivables_doc_nbr = prompt_open_invoice_or_manual(open_invoices)
    receivables_doc_type = "PMT"
    receivables_ext_doc = prompt_check_number()
    comment = prompt_text("Comment")

    debug_print(debug, f"Selected/entered invoice number: {receivables_doc_nbr}")
    debug_print(debug, f"Generated ExtDoc for mobile deposit: {receivables_ext_doc}")
    debug_print(debug, f"Mobile deposit comment: {comment}")

    entry = build_mobile_deposit_entry(
        entry_date=entry_date,
        amount=amount,
        credit_account=credit_account,
        description=description,
        comment=comment,
        receivables_doc_type=receivables_doc_type,
        receivables_doc_nbr=receivables_doc_nbr,
        receivables_ext_doc=receivables_ext_doc,
    )

    debug_print(debug, f"Built mobile deposit entry with {len(entry.lines)} lines")
    return entry


def handle_auto_deposit_entry(
    client: SheetsClient,
    valid_accounts: list[str],
    debug: bool = False,
) -> JournalEntry:
    print("\nAuto Deposit to Checking")
    entry_date = prompt_date()
    amount = prompt_amount()
    description = prompt_text("Description", default="Auto Deposit to Checking")

    debug_print(debug, f"Auto deposit date entered: {entry_date}")
    debug_print(debug, f"Auto deposit amount entered: {amount}")
    debug_print(debug, f"Auto deposit description: {description}")

    credit_account = prompt_account_by_prefix(
        valid_accounts,
        prefix="Rcvbls",
        label="Select receivables account",
    )
    debug_print(debug, f"Auto deposit receivables account selected: {credit_account}")

    open_invoices = client.get_open_invoices_for_account(credit_account)
    debug_print(debug, f"Open invoices found: {len(open_invoices)}")

    receivables_doc_nbr = prompt_open_invoice_or_manual(open_invoices)
    receivables_doc_type = "ACH"
    receivables_ext_doc = prompt_transaction_number()
    comment = prompt_text("Comment")

    debug_print(debug, f"Selected/entered invoice number: {receivables_doc_nbr}")
    debug_print(debug, f"Generated ExtDoc for auto deposit: {receivables_ext_doc}")
    debug_print(debug, f"Auto deposit comment: {comment}")

    entry = build_mobile_deposit_entry(
        entry_date=entry_date,
        amount=amount,
        credit_account=credit_account,
        description=description,
        comment=comment,
        receivables_doc_type=receivables_doc_type,
        receivables_doc_nbr=receivables_doc_nbr,
        receivables_ext_doc=receivables_ext_doc,
    )

    debug_print(debug, f"Built auto deposit entry with {len(entry.lines)} lines")
    return entry


def handle_recurring_entry(client: SheetsClient, debug: bool = False) -> JournalEntry:
    print("\nPost Recurring Entry")
    client.display_recurring_entries()

    seq = prompt_seq_number()
    debug_print(debug, f"Recurring Seq selected: {seq}")

    entry = client.get_recurring_entry_by_seq(seq)
    debug_print(debug, f"Loaded recurring entry with {len(entry.lines)} lines")

    entry.entry_date = prompt_date()
    debug_print(debug, f"Recurring entry date overridden to: {entry.entry_date}")

    if len(entry.lines) == 2:
        default_amount = _first_nonzero_amount(entry)
        debug_print(debug, f"Two-line recurring entry default amount: {default_amount}")
        new_amount = prompt_amount_with_default("Amount", default_amount)
        debug_print(debug, f"Two-line recurring entry overridden amount: {new_amount}")
        _apply_single_amount(entry, new_amount)
    else:
        debug_print(debug, "Multi-line recurring entry: prompting per nonzero line")
        _prompt_line_amounts(entry, debug=debug)

    validate_entry(entry)
    debug_print(debug, "Recurring entry validated successfully")
    return entry


def _first_nonzero_amount(entry: JournalEntry) -> Decimal:
    for line in entry.lines:
        if line.debit != Decimal("0.00"):
            return line.debit
        if line.credit != Decimal("0.00"):
            return line.credit
    return Decimal("0.00")


def _apply_single_amount(entry: JournalEntry, amount: Decimal) -> None:
    for line in entry.lines:
        if line.debit != Decimal("0.00"):
            line.debit = amount
        if line.credit != Decimal("0.00"):
            line.credit = amount


def _prompt_line_amounts(entry: JournalEntry, debug: bool = False) -> None:
    for line in entry.lines:
        if line.debit != Decimal("0.00"):
            label = f"Debit amount for {line.account}"
            line.debit = prompt_amount_with_default(label, line.debit)
            debug_print(debug, f"Updated debit for {line.account}: {line.debit}")
        elif line.credit != Decimal("0.00"):
            label = f"Credit amount for {line.account}"
            line.credit = prompt_amount_with_default(label, line.credit)
            debug_print(debug, f"Updated credit for {line.account}: {line.credit}")
