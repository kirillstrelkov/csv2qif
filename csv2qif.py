import codecs
import json
import os
from argparse import ArgumentParser
from collections import namedtuple

from loguru import logger

from finance_utils.csv_format import CSVParser, get_csv_format
from finance_utils.file_utils import get_files_and_subfiles, save_file


def get_qif_trans(gnucash_trans, account_from=None):
    trans = []
    Transaction = namedtuple(
        "QIFTransaction", ["date", "amount", "description", "account"]
    )
    for tran in gnucash_trans:
        if account_from == tran.account:
            trans_as_str = ", ".join(
                [str(getattr(tran, field)) for field in tran._fields]
            )
            logger.warning(f"SKIP: Found transaction with same account: {trans_as_str}")
        else:
            trans.append(
                Transaction(
                    tran.date,
                    tran.increase if type(tran.increase) == float else -tran.decrease,
                    tran.description,
                    tran.account,
                )
            )
    return trans


def qif_trans_to_string(qif_trans, format, gnucash_account):
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


def get_qif_trans_from_csv(
    path_or_paths,
    format,
    mappings,
    skip_descriptions,
    skip_currencies=None,
    account_from=None,
):
    parser = CSVParser(format, mappings, skip_descriptions, skip_currencies)
    if type(path_or_paths) == str:
        paths = [path_or_paths]
    else:
        paths = path_or_paths

    gnucash_trans = []
    for path in paths:
        gnucash_trans += parser.get_gnucash_transactions(path)

    return get_qif_trans(gnucash_trans, account_from=account_from)


def _get_qif_trans(input, config, format, gnucash_account_alias):
    csv_format = get_csv_format(config, format)
    config_json = json.load(codecs.open(config))
    gnucash_account = config_json["gnucash_aliases"][gnucash_account_alias]
    mappings = config_json["mappings"]
    skip_descriptions = config_json.get("skip_descriptions")
    skip_currencies = config_json.get("skip_currencies")

    if type(input) == list:
        inputs = input
    elif type(input) == str and os.path.isdir(input):
        inputs = get_files_and_subfiles(input, ".csv")
        inputs += get_files_and_subfiles(input, ".CSV")
    else:
        inputs = [input]

    qif_trans = []
    for input in inputs:
        qif_trans += get_qif_trans_from_csv(
            input,
            csv_format,
            mappings,
            skip_descriptions,
            skip_currencies=skip_currencies,
            account_from=gnucash_account,
        )

    # NOTE: set is used to remove duplicates - ordered is not preserved!
    qif_trans_no_dup = list(set(qif_trans))
    if len(qif_trans_no_dup) != len(qif_trans):
        logger.warning(
            f"Found multiple duplicated transactions: all = {len(qif_trans)}, without duplicates = {len(qif_trans_no_dup)}"
        )
    return sorted(qif_trans_no_dup, key=lambda q: (q.date, q.description))


def csv2qif(input, config, format, gnucash_account_alias):
    # TODO: add check for config mappings and warn if found one

    gnucash_account = json.load(codecs.open(config))["gnucash_aliases"][
        gnucash_account_alias
    ]
    qif_trans = _get_qif_trans(input, config, format, gnucash_account_alias)

    csv_format = get_csv_format(config, format)
    return qif_trans_to_string(qif_trans, csv_format, gnucash_account)


def save_qif(input, output, config, format, gnucash_account_alias):
    save_file(output, csv2qif(input, config, format, gnucash_account_alias))


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


# TODO: add check for data - parsing and formatting should be possible
