import os
import json
import codecs
from pprint import pprint
from unittest import TestCase

from csv2qif import get_qif_trans_from_csv
from finance_utils.accounts.base import BaseAccount, load_bank
from finance_utils.file_utils import get_files_and_subfiles


class DataTestCase(TestCase):
    DATA_FOLDER = ""
    BANK = None

    def get_data_file(self, name):
        assert self.TYPE in ("public", "private")
        data_folder = os.path.abspath(
            os.path.join(os.path.dirname(__file__), self.TYPE, "data")
        )
        found_files = get_files_and_subfiles(data_folder, name)
        assert len(found_files) == 1
        return found_files[0]

    def assert_qif_trans(
        self, filename, expected_nr_qifs, expected_nr_imbalanced, bank=None
    ):
        bank = bank or self.BANK
        assert bank is not None
        path = self.get_data_file(self.DATA_FOLDER + filename)

        qifs = get_qif_trans_from_csv(
            path,
            load_bank(self.CONFIG, bank),
            json.load(codecs.open(self.CONFIG))["mappings"],
        )
        imbalanced = [qif for qif in qifs if "imbalance" in qif.account.lower()]

        if len(imbalanced) > 0:
            pprint(imbalanced)

        assert len(imbalanced) == expected_nr_imbalanced
        assert len(qifs) == expected_nr_qifs


class GnucashTestCase(DataTestCase):
    BANK = None
    BAD_TRANS_RATIO = 0.3

    def assert_parse_and_format(self, filename, total):
        bank = load_bank(
            self.CONFIG,
            self.BANK,
        )
        mappings = json.load(codecs.open(self.CONFIG))["mappings"]

        trans = BaseAccount(bank, mappings).get_gnucash_transactions(
            self.get_data_file(filename)
        )
        assert len(trans) == total

        trans = [t for t in trans if t.account == ""]
        assert len(trans) <= total * self.BAD_TRANS_RATIO


class PrivateConfig(object):
    CONFIG = os.path.join(os.path.dirname(__file__), "private/config.json")
    TYPE = "private"


class PublicConfig(object):
    CONFIG = os.path.join(os.path.dirname(__file__), "public/config.json")
    TYPE = "public"
