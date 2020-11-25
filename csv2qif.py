from collections import namedtuple

from finance_utils.file_utils import get_files_and_subfiles, save_file
from finance_utils.csv_format import CSVParser, get_csv_format
import codecs
import json
from argparse import ArgumentParser
import os


def get_qif_trans(gnucash_trans):
    trans = []
    Transaction = namedtuple(
        "QIFTransaction", ["date", "amount", "description", "account"]
    )
    for gnucas_tran in gnucash_trans:
        trans.append(
            Transaction(
                gnucas_tran.date,
                gnucas_tran.increase
                if type(gnucas_tran.increase) == float
                else -gnucas_tran.decrease,
                gnucas_tran.description,
                gnucas_tran.account,
            )
        )
    return trans


def qif_trans_to_string(qif_trans, bank, gnucash_account):
    header = """!Account
N{account_name}
^"""
    tran_template = """!Type:Bank
D{date}
T{amount}
P{description}
L{account}
^"""
    output = [header.format(account_name=gnucash_account)]
    for tran in qif_trans:
        if tran.date:
            # d,m,y = tran.date.split('.')
            output.append(
                tran_template.format(
                    # date="{}-{}-{}".format(y, d, m),
                    date=tran.date,
                    amount=tran.amount,
                    description=tran.description,
                    account=tran.account,
                )
            )
    return "\n".join(output)


def get_qif_trans_from_csv(path, bank, mappings, skip_descriptions):
    gnucash_trans = CSVParser(
        bank, mappings, skip_descriptions
    ).get_gnucash_transactions(path)
    return get_qif_trans(gnucash_trans)


def csv2qif(input, config, bank_name, gnucash_account_alias):
    bank = get_csv_format(config, bank_name)
    config = json.load(codecs.open(config))
    gnucash_account = config["gnucash_aliases"][gnucash_account_alias]
    mappings = config["mappings"]
    skip_descriptions = config.get("skip_descriptions")

    if os.path.isdir(input):
        inputs = get_files_and_subfiles(input, ".csv")
    else:
        inputs = [input]

    qif_trans = []
    for input in inputs:
        qif_trans += get_qif_trans_from_csv(input, bank, mappings, skip_descriptions)

    return qif_trans_to_string(qif_trans, bank, gnucash_account)


def save_qif(input, output, config, bank_name, gnucash_account_alias):
    save_file(output, csv2qif(input, config, bank_name, gnucash_account_alias))


def __main():
    parser = ArgumentParser(description="Convert CSV file to QIF file.")
    parser.add_argument(
        "input",
        help="path to input CSV file",
    )
    parser.add_argument(
        "output",
        help="path to output QIF file",
    )
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="path to config file",
    )
    parser.add_argument(
        "-f",
        "--format",
        required=True,
        help="format to be used from config file",
    )
    parser.add_argument(
        "-a",
        "--account",
        required=True,
        help="key in gnucash_aliases which is used as account name in QIF file",
    )

    args = parser.parse_args()
    save_qif(args.input, args.output, args.config, args.format, args.account)


if __name__ == "__main__":
    __main()
