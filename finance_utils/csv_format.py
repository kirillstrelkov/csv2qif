"""Functions to work with CSV file."""

import codecs
import csv
import json
import re
from collections import namedtuple
from collections.abc import Iterable
from pathlib import Path
from typing import Any, NamedTuple

from finance_utils.common import (
    GnuCashTransaction,
    get_account_from,
    match_description,
    text_to_field,
)


class CSVFormat(NamedTuple):
    """Transaction class that holds GnuCash information."""

    name: str
    encoding: str
    delimiter: str
    description: str
    date: str | None


def get_csv_format(path: str, format_name: str) -> CSVFormat:
    """Return CSVFormat object from JSON config file."""
    for format_obj in json.load(codecs.open(path, encoding="utf8")).get("formats", []):
        if format_obj["name"] == format_name:
            return CSVFormat(*[format_obj[field] for field in CSVFormat._fields])

    msg = f"Wrong format name: {format_name}"
    raise ValueError(msg)


class CSVParser:
    """Class to parse CSV file."""

    def __init__(
        self,
        format_: str,
        mappings: dict[str, list[str]],
        skip_descriptions: list[str],
        skip_currencies: list[str] | None = None,
    ) -> None:
        """Initialize object."""
        self.format = format_
        self.mappings = mappings
        self.skip_descriptions = skip_descriptions
        self.skip_currencies = skip_currencies or []

    def __get_transaction_value(
        self,
        transaction: Any,  # noqa: ANN401
        field: str,
    ) -> Any:  # noqa: ANN401
        field_value = getattr(self.format, field, None)
        if isinstance(field_value, list):
            value = " ".join(
                [
                    self.__fix_text(getattr(transaction, text_to_field(v)))
                    for v in field_value
                    if hasattr(transaction, v)
                ],
            )
        elif field_value:
            value = getattr(transaction, field_value)
        else:
            value = getattr(transaction, field, None)

        if field_value:
            value = self.__fix_text(value)

        return value

    def __fix_text(self, text: str) -> str:
        text = re.sub(r"[\t;,\s]+", " ", text)
        text = re.sub(r"^[\"']+", "", text)
        return re.sub(r"[\"']+$", "", text)

    def _format_gnucash_transaction(
        self,
        transaction: Any,  # noqa: ANN401
    ) -> GnuCashTransaction:
        increase = ""
        decrease = ""
        desc = self.__get_transaction_value(transaction, "description")
        debit_credit = self.__get_transaction_value(transaction, "debit_credit")
        date = self.__get_transaction_value(transaction, "date")

        for skip_desc in self.skip_descriptions:
            if match_description(desc, skip_desc):
                return None

        amount = round(
            float(
                self.__get_transaction_value(transaction, "amount").replace(",", "."),
            ),
            2,
        )

        if (
            self.__get_transaction_value(transaction, "currency")
            in self.skip_currencies
        ):
            return None

        # Note: special case for Estonia - convert transaction from EEK to EUR
        if self.__get_transaction_value(transaction, "currency") == "EEK":
            old_amount = amount
            amount = round(amount / 15.6466, 2)
            desc += f" {old_amount} EEK -> {amount} EUR"

        if debit_credit:
            if debit_credit == "K":
                increase = amount
            else:
                decrease = abs(amount)
        elif amount > 0:
            increase = amount
        else:
            decrease = abs(amount)

        account = get_account_from(desc, self.mappings)
        return GnuCashTransaction(date, desc, account, increase, decrease)

    def _parse_bank_csv(self, iterable: Iterable[str]) -> list[Any]:
        # TODO: use pandas read_csv  # noqa: TD002, TD003, FIX002
        trans = []
        Transaction = None  # noqa: N806

        for row in csv.reader(iterable, delimiter=self.format.delimiter):
            if len(row) == 1 and row[0].count("\t") > 4:  # noqa: PLR2004
                row = row[0].split("\t")  # noqa: PLW2901
            if Transaction:
                t = Transaction(*row)
                trans.append(t)
            else:
                names = [text_to_field(r) if r else "x" for r in row]
                Transaction = namedtuple("Transaction", names)  # noqa: PYI024

        return trans

    def get_gnucash_transactions(self, path: str) -> list[GnuCashTransaction]:
        """Return list of GnuCash transactions from CSV file."""
        trans = []
        if Path(path).is_file():
            with codecs.open(
                path,
                "rb",
                encoding=self.format.encoding,
                errors="replace",
            ) as f:
                trans += self._parse_bank_csv(f)
        else:
            trans += self._parse_bank_csv(path.split("\n"))

        formatted_trans = [self._format_gnucash_transaction(tran) for tran in trans]
        gnucash_trans = [t for t in formatted_trans if t is not None]
        skipped_trans = [t for t in formatted_trans if t is None]

        assert len(trans) == len(gnucash_trans) + len(skipped_trans)  # noqa: S101

        return gnucash_trans
