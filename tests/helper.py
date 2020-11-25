import os
import json
import codecs
from pprint import pprint
from unittest import TestCase

from csv2qif import get_qif_trans_from_csv
from finance_utils.csv_format import CSVParser, get_csv_format
from finance_utils.file_utils import get_files_and_subfiles


class DataTestCase(TestCase):
    DATA_FOLDER = ""
    CSV_FORMAT = None

    def get_data_file(self, name):
        assert self.TYPE in ("public", "private")
        data_folder = os.path.abspath(
            os.path.join(os.path.dirname(__file__), self.TYPE, "data")
        )
        found_files = get_files_and_subfiles(data_folder, name)
        assert len(found_files) == 1
        return found_files[0]

    def assert_qif_trans(
        self, filename, expected_nr_qifs, expected_nr_imbalanced, csv_format=None
    ):
        csv_format = csv_format or self.CSV_FORMAT
        assert csv_format is not None

        path = self.get_data_file(self.DATA_FOLDER + filename)
        config = json.load(codecs.open(self.CONFIG))

        qifs = get_qif_trans_from_csv(
            path,
            get_csv_format(self.CONFIG, csv_format),
            config["mappings"],
            config.get("skip_descriptions"),
        )
        imbalanced = [qif for qif in qifs if "imbalance" in qif.account.lower()]

        if len(imbalanced) > 0:
            pprint(imbalanced)

        assert len(imbalanced) == expected_nr_imbalanced
        assert len(qifs) == expected_nr_qifs


class GnucashTestCase(DataTestCase):
    CSV_FORMAT = None
    BAD_TRANS_RATIO = 0.3

    def assert_parse_and_format(self, filename, total):
        bank = get_csv_format(
            self.CONFIG,
            self.CSV_FORMAT,
        )
        config = json.load(codecs.open(self.CONFIG))
        mappings = config["mappings"]
        skip_descriptions = config.get("skip_descriptions")

        trans = CSVParser(bank, mappings, skip_descriptions).get_gnucash_transactions(
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
