import re
from collections import namedtuple

GnuCashTransaction = namedtuple(
    "GnuCashTransaction", ["date", "description", "account", "increase", "decrease"]
)


def text_to_field(text):
    return re.sub(r"\W", "_", text).lower()


def match_description(description, regexp_or_string):
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
