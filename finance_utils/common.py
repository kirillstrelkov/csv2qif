import codecs
import csv
import os
import re
from collections import namedtuple
from pprint import pprint

GnuCashTransaction = namedtuple(
    "GnuCashTransaction", ["date", "description", "account", "increase", "decrease"]
)


def __get_transations(iterable, bank):
    trans = []
    Transaction = None

    delimiter = bank.delimiter
    for row in csv.reader(iterable, delimiter=delimiter):
        if len(row) == 1 and row[0].count("\t") > 4:
            row = row[0].split("\t")
        if Transaction:
            t = Transaction(*row)
            trans.append(t)
        else:
            names = ["x" if len(r) == 0 else re.sub(r"\W", "_", r).lower() for r in row]
            Transaction = namedtuple("Transaction", names)

    return trans


def get_transactions_from_csv(path_or_csv, bank):
    trans = []
    if os.path.isfile(path_or_csv):
        with codecs.open(path_or_csv, "rb", encoding="utf8", errors="replace") as f:
            trans += __get_transations(f, bank)
    else:
        trans += __get_transations(path_or_csv.split("\n"), bank)

    return trans


def format_date(date):
    # TODO parse to correct date
    return date


def get_account_from(tran_desc, mappings):
    for account, descs in mappings.items():
        for desc in descs:
            if desc.upper() in tran_desc.upper():
                return account

    return "Imbalance-EUR"


def save_transactions(trans, path):
    with codecs.open(path, "wb", encoding="utf8") as f:
        writer = csv.writer(f, delimiter="\t")
        for tran in trans:
            writer.writerow(tran)

    pprint("New file created with gnucash transactions: " + path)
