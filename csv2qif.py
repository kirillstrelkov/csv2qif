"""Script that converts CSV to QIF format."""
import codecs
import json
from argparse import ArgumentParser
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Any, NamedTuple

from loguru import logger

from finance_utils.csv_format import CSVParser, get_csv_format
from finance_utils.file_utils import get_files_and_subfiles, save_file


class QIFTransaction(NamedTuple):
    """Transaction class that holds QIF information."""

    date: str | None
    amount: float | int | None
    description: str | None
    account: str | None


def get_qif_trans(
    gnucash_trans: list[Any],
    account_from: str | None = None,
) -> list[QIFTransaction]:
    """Get QIF transactions from GnuCash transactions."""
    trans = []
    for tran in gnucash_trans:
        if account_from == tran.account:
            trans_as_str = ", ".join(
                [str(getattr(tran, field)) for field in tran._fields],
            )
            logger.warning(f"SKIP: Found transaction with same account: {trans_as_str}")
        else:
            trans.append(
                QIFTransaction(
                    tran.date,
                    tran.increase
                    if isinstance(tran.increase, float)
                    else -tran.decrease,
                    tran.description,
                    tran.account,
                ),
            )
    return trans


def qif_trans_to_string(
    qif_trans: list[Any],
    _format: str,
    gnucash_account: str,
) -> str:
    """Format all QIF transactions to single string."""
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
    output += [
        tran_template.format(
            date=tran.date,
            amount=tran.amount,
            description=tran.description,
            account=tran.account,
        )
        for tran in qif_trans
        if tran.date
    ]
    return "\n".join(output)


def get_qif_trans_from_csv(  # noqa: PLR0913
    path_or_paths: str | list[Any],
    format_: str,
    mappings: dict[str, str],
    skip_descriptions: list[str],
    skip_currencies: list[str] | None = None,
    account_from: str | None = None,
) -> list[QIFTransaction]:
    """Get QIF transactions from CSV file(s)."""
    parser = CSVParser(format_, mappings, skip_descriptions, skip_currencies)
    paths = [path_or_paths] if isinstance(path_or_paths, str) else path_or_paths

    # TODO: quick fix - small speed up, profile to find bottleneck.  # noqa: TD002, TD003, FIX002, E501
    path_trans = Pool(cpu_count() - 1).map(parser.get_gnucash_transactions, paths)
    gnucash_trans = [tran for sub_list in path_trans for tran in sub_list]

    return get_qif_trans(gnucash_trans, account_from=account_from)


def _get_qif_trans(
    input_path: str | list[Any],
    config_path: str,
    format_: str,
    gnucash_account_alias: str,
) -> list[QIFTransaction]:
    csv_format = get_csv_format(config_path, format_)
    config_json = json.load(codecs.open(config_path))
    gnucash_account = config_json["gnucash_aliases"][gnucash_account_alias]
    mappings = config_json["mappings"]
    skip_descriptions = config_json.get("skip_descriptions")
    skip_currencies = config_json.get("skip_currencies")

    if isinstance(input_path, list):
        inputs = input_path
    elif isinstance(input_path, str) and Path(input_path).is_dir():
        inputs = get_files_and_subfiles(input_path, ".csv")
        inputs += get_files_and_subfiles(input_path, ".CSV")
    else:
        inputs = [input_path]

    qif_trans = []
    for input_path in inputs:
        qif_trans += get_qif_trans_from_csv(
            input_path,
            csv_format,
            mappings,
            skip_descriptions,
            skip_currencies=skip_currencies,
            account_from=gnucash_account,
        )

    # NOTE: set is used to remove duplicates - ordered is not preserved!
    qif_trans_no_dup = list(set(qif_trans))
    if len(qif_trans_no_dup) != len(qif_trans):
        diff = "\n".join(
            [str(trans) for trans in qif_trans_no_dup if qif_trans.count(trans) > 1],
        )
        logger.warning(
            "Found multiple duplicated transactions: all = {}, "
            "without duplicates = {}:\n{}",
            len(qif_trans),
            len(qif_trans_no_dup),
            diff,
        )
    return sorted(qif_trans_no_dup, key=lambda q: (q.date, q.description))


def csv2qif(
    input_path: str | list[Any],
    config_path: str,
    format_: str,
    gnucash_account_alias: str,
) -> str:
    """Format transactions from CSV file to string with QIF transactions."""
    # TODO: add check for config mappings and warn if found one  # noqa: TD002, TD003, FIX002, E501

    gnucash_account = json.load(codecs.open(config_path))["gnucash_aliases"][
        gnucash_account_alias
    ]
    qif_trans = _get_qif_trans(input_path, config_path, format_, gnucash_account_alias)

    csv_format = get_csv_format(config_path, format_)
    return qif_trans_to_string(qif_trans, csv_format, gnucash_account)


def save_qif(
    input_path: str | list[Any],
    output: str,
    config_path: str,
    format_: str,
    gnucash_account_alias: str,
) -> None:
    """Read CSV files and save transactions to QIF file."""
    save_file(output, csv2qif(input_path, config_path, format_, gnucash_account_alias))


def __main() -> None:
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


# TODO: add check for data - parsing and formatting should be possible  # noqa: TD002, TD003, FIX002, E501
