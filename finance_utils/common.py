import codecs
import json
import re
from typing import NamedTuple


class GnuCashTransaction(NamedTuple):
    """Transaction class that holds GnuCash information."""

    date: str | None
    description: str | None
    account: str | None
    increase: float | int | None
    decrease: float | int | None


def get_config_value(config_path: str, key: str) -> str | list[str]:
    """Get value from JSON file."""
    config = json.load(codecs.open(config_path))
    return config.get(key)


def get_mappings_conflicts(config_path: str) -> list[str]:
    """Get list of conflicts."""
    conflicts = []

    mappings = get_config_value(config_path, "mappings")

    index1 = 0
    for account1, regexps1 in mappings.items():
        index2 = 0
        for account2, regexps2 in mappings.items():
            if account1 == account2 and regexps1 == regexps2:
                continue

            for regexp1 in regexps1:
                for regexp2 in regexps2:
                    if regexp1 == regexps2:
                        continue

                    if match_description(regexp1, regexp2) and index1 > index2:
                        conflicts.append(
                            f"Found match between '{account1}, {regexp1}, {index1}'"
                            f" and '{account2}, {regexp2}, {index2}'",
                        )

            index2 += 1
        index1 += 1

    return conflicts


def text_to_field(text: str) -> str:
    """Format string."""
    return "_".join(re.findall(r"\w+", text)).lower()


def match_description(description: str, regexp_or_string: str) -> bool | None:
    """Return True if text matches string or regexp else False."""
    # TODO: add check for special characters for regexp  # noqa: TD002, FIX002, TD003
    try:
        match = re.search(regexp_or_string, description, re.IGNORECASE)
    except re.error:
        match = None

    if match is None:
        match = regexp_or_string.lower() in description.lower()

    return bool(match)


def get_account_from(tran_desc: str, mappings: dict[str, list[str]]) -> str:
    """Return account based on descrition and mappings."""
    for account, descs in mappings.items():
        for desc in descs:
            if match_description(tran_desc, desc):
                return account

    return "Imbalance-EUR"
