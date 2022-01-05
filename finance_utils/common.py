import codecs
import json
import re
from collections import namedtuple

GnuCashTransaction = namedtuple(
    "GnuCashTransaction", ["date", "description", "account", "increase", "decrease"]
)


def get_config_value(config, key):
    assert config is not None
    config = json.load(codecs.open(config))
    return config.get(key)


def get_mappings_conflicts(config_path):
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
                            f"Found match between '{account1}, {regexp1}, {index1}' and '{account2}, {regexp2}, {index2}'"
                        )

            index2 += 1
        index1 += 1

    return conflicts


def text_to_field(text):
    return re.sub(r"\W", "_", text).lower()


def match_description(description, regexp_or_string):
    # TODO: add check for special characters for regexp
    try:
        match = re.search(regexp_or_string, description, re.IGNORECASE)
    except re.error:
        match = None

    if match is None:
        match = regexp_or_string.lower() in description.lower()

    return match


def get_account_from(tran_desc, mappings):
    for account, descs in mappings.items():
        for desc in descs:
            if match_description(tran_desc, desc):
                return account

    return "Imbalance-EUR"
