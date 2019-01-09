import codecs
import csv
import os
import re
import json
from collections import namedtuple
from finance_utils.common import format_date, get_account_from, GnuCashTransaction

Bank = namedtuple("Bank", ["name", "encoding", "delimiter", "description", "date"])


def load_bank(path, name):
    for bank in json.load(codecs.open(path, encoding="utf8")).get("banks", []):
        if bank["name"] == name:
            return Bank(*[bank[field] for field in Bank._fields])
    assert False, f"Wrong name: {name}"


class BaseAccount(object):
    def __init__(self, bank, mappings=None):
        self.bank = bank
        self.mappings = mappings

    def __get_transaction_value(self, transaction, field):
        bank_field_value = getattr(self.bank, field, None)
        if type(bank_field_value) == list:
            value = " ".join([getattr(transaction, v) for v in bank_field_value])
            if field == "description":
                value = re.sub("[\t;,\s]+", " ", value)
        elif bank_field_value:
            value = getattr(transaction, bank_field_value)
        else:
            value = getattr(transaction, field, None)

        return value

    def _format_gnucash_transaction(self, transaction):
        increase = ""
        decrease = ""
        desc = self.__get_transaction_value(transaction, "description")
        debit_credit = self.__get_transaction_value(transaction, "debit_credit")
        date = self.__get_transaction_value(transaction, "date")

        bad_descs = ["Opening balance", "Turnover", "closing balance"]
        for bad_desc in bad_descs:
            if bad_desc in desc:
                return None

        if self.__get_transaction_value(transaction, "currency") != "EUR":
            return None

        account = get_account_from(desc, self.mappings)
        amount = round(
            float(
                self.__get_transaction_value(transaction, "amount").replace(",", ".")
            ),
            2,
        )
        if debit_credit:
            if debit_credit == "K":
                increase = amount
            else:
                decrease = abs(amount)
        elif amount > 0:
            increase = amount
        else:
            decrease = abs(amount)

        return GnuCashTransaction(date, desc, account, increase, decrease)

    def _parse_bank_csv(self, iterable):
        # TODO: use pandas read_csv
        trans = []
        Transaction = None

        for row in csv.reader(iterable, delimiter=self.bank.delimiter):
            if len(row) == 1 and row[0].count("\t") > 4:
                row = row[0].split("\t")
            if Transaction:
                t = Transaction(*row)
                trans.append(t)
            else:
                names = [
                    "x" if len(r) == 0 else re.sub(r"\W", "_", r).lower() for r in row
                ]
                Transaction = namedtuple("Transaction", names)

        return trans

    def get_gnucash_transactions(self, path):
        trans = []
        if os.path.isfile(path):
            with codecs.open(
                path, "rb", encoding=self.bank.encoding, errors="replace"
            ) as f:
                trans += self._parse_bank_csv(f)
        else:
            trans += self._parse_bank_csv(path.split("\n"))

        formatted_trans = [self._format_gnucash_transaction(tran) for tran in trans]
        gnucash_trans = [t for t in formatted_trans if t is not None]
        skipped_trans = [t for t in formatted_trans if t is None]

        assert len(trans) == len(gnucash_trans) + len(skipped_trans)

        return gnucash_trans

    def save_gnucash_csv(self, input_path, output_path):
        gnucase_trans = self.get_gnucash_transactions(input_path)

        with codecs.open(output_path, "wb", encoding="utf8") as f:
            writer = csv.writer(f, delimiter="\t")
            for tran in gnucase_trans:
                writer.writerow(tran)

        print("New file created with gnucash transactions: " + output_path)
