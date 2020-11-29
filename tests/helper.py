import os
import json
import codecs
from unittest import TestCase
from loguru import logger

from csv2qif import get_qif_trans_from_csv
from finance_utils.csv_format import CSVParser, get_csv_format
from finance_utils.file_utils import get_files_and_subfiles
import re


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

        qif_account = self.get_config_value("gnucash_aliases").get(self.GNUCASH_ALIAS)
        assert qif_account

        path = self.get_data_file(self.DATA_FOLDER + filename)

        trans = get_qif_trans_from_csv(
            path,
            get_csv_format(self.CONFIG, csv_format),
            self.get_config_value("mappings"),
            self.get_config_value("skip_descriptions"),
            skip_currencies=self.get_config_value("skip_currencies"),
            account_from=qif_account,
        )
        self.__assert_imbalanced_and_counts(
            trans, expected_nr_imbalanced, expected_nr_qifs
        )

        self.__assert_same_account(trans, qif_account)

        self.__assert_descriptions(trans)

    def __assert_imbalanced_and_counts(
        self, trans, expected_nr_imbalanced, expected_nr_qifs
    ):
        imbalanced = [tran for tran in trans if "imbalance" in tran.account.lower()]
        for im in imbalanced:
            logger.error(im)

        assert len(imbalanced) == expected_nr_imbalanced
        assert len(trans) == expected_nr_qifs

    def __assert_descriptions(self, trans):
        for tran in trans:
            for char in ['"', "'"]:
                assert not tran.description.startswith(char)
                assert not tran.description.endswith(char)
            assert not re.search(r"\s{2,}", tran.description)

    def __assert_same_account(self, trans, account):
        trans_to_same_account = [t for t in trans if t.account == account]
        for t in trans_to_same_account:
            logger.error(t)
        assert len(trans_to_same_account) == 0

    def get_config_value(self, key):
        assert self.CONFIG is not None
        config = json.load(codecs.open(self.CONFIG))
        return config.get(key)


class GnucashTestCase(DataTestCase):
    CSV_FORMAT = None
    BAD_TRANS_RATIO = 0.3

    def assert_parse_and_format(self, filename, total):
        bank = get_csv_format(
            self.CONFIG,
            self.CSV_FORMAT,
        )
        mappings = self.get_config_value("mappings")
        skip_descriptions = self.get_config_value("skip_descriptions")
        skip_currencies = self.get_config_value("skip_currencies")

        trans = CSVParser(
            bank, mappings, skip_descriptions, skip_currencies
        ).get_gnucash_transactions(self.get_data_file(filename))
        assert len(trans) == total

        trans = [t for t in trans if t.account == ""]
        assert len(trans) <= total * self.BAD_TRANS_RATIO


class PrivateConfig(object):
    CONFIG = os.path.join(os.path.dirname(__file__), "private/config.json")
    TYPE = "private"


class PublicConfig(object):
    CONFIG = os.path.join(os.path.dirname(__file__), "public/config.json")
    TYPE = "public"
