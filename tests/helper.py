"""Helper functions for tests."""
import contextlib
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from pprint import pformat
from typing import Any
from unittest import TestCase

from loguru import logger

from csv2qif import get_qif_trans_from_csv
from finance_utils.common import get_config_value
from finance_utils.csv_format import CSVParser, get_csv_format
from finance_utils.file_utils import get_files_and_subfiles


class DataTestCase(TestCase):
    """Base TestCase to work with data folder."""

    DATA_FOLDER = ""
    CSV_FORMAT = None

    def get_data_files(self, filename: str | None = None) -> list[Path]:
        """Return list of data files."""
        assert self.TYPE in ("public", "private")
        root_dir = Path(__file__).parent / self.TYPE / "data"

        if filename:
            found_files = get_files_and_subfiles(root_dir, filename)
        else:
            found_files = get_files_and_subfiles(
                root_dir / self.DATA_FOLDER,
                ".csv",
            )
            found_files += get_files_and_subfiles(
                root_dir / self.DATA_FOLDER,
                ".CSV",
            )

        assert len(found_files) >= 1
        return found_files

    def assert_qif_trans(
        self,
        expected_nr_qifs: int,
        expected_nr_imbalanced: int,
        csv_format: str | None = None,
        filename: str | None = None,
    ) -> None:
        """Assert transactions."""
        csv_format = csv_format or self.CSV_FORMAT
        assert csv_format is not None

        qif_account = get_config_value(self.CONFIG, "gnucash_aliases").get(
            self.GNUCASH_ALIAS,
        )
        assert qif_account

        files = self.get_data_files(filename)

        trans = get_qif_trans_from_csv(
            files,
            get_csv_format(self.CONFIG, csv_format),
            get_config_value(self.CONFIG, "mappings"),
            get_config_value(self.CONFIG, "skip_descriptions"),
            skip_currencies=get_config_value(self.CONFIG, "skip_currencies"),
            account_from=qif_account,
        )
        self.__assert_imbalanced_and_counts(
            trans,
            expected_nr_imbalanced,
            expected_nr_qifs,
        )

        self.__assert_same_account(trans, qif_account)

        self.__assert_descriptions(trans)

    def __assert_imbalanced_and_counts(
        self,
        trans: list[Any],
        expected_nr_imbalanced: int,
        expected_nr_qifs: int,
    ) -> None:
        imbalanced = [tran for tran in trans if "imbalance" in tran.account.lower()]

        with contextlib.suppress(Exception):
            imbalanced = sorted(
                imbalanced,
                key=lambda t: datetime.strptime(t.date, "%d.%m.%Y"),  # noqa: DTZ007
            )

        for im in imbalanced:
            logger.error(im)

        descriptions = [
            t.description[
                0 : (
                    t.description.index(t.date[-4:])
                    if t.date[-4:] in t.description
                    else -1
                )
            ]
            for t in imbalanced
        ]
        logger.debug("Top 10 most common descriptions:")
        logger.debug(pformat(Counter(descriptions).most_common(10)))

        assert len(imbalanced) == expected_nr_imbalanced
        assert len(trans) == expected_nr_qifs

    def __assert_descriptions(self, trans: list[Any]) -> None:
        for tran in trans:
            for char in ['"', "'"]:
                assert not tran.description.startswith(char)
                assert not tran.description.endswith(char)
            assert not re.search(r"\s{2,}", tran.description)

    def __assert_same_account(self, trans: list[Any], account: str) -> None:
        trans_to_same_account = [t for t in trans if t.account == account]
        for t in trans_to_same_account:
            logger.error(t)
        assert len(trans_to_same_account) == 0


class GnucashTestCase(DataTestCase):
    """Base TestCase class for GnuCash transactions."""

    CSV_FORMAT = None
    BAD_TRANS_RATIO = 0.1

    def assert_parse_and_format(self, filename: str, total: int) -> None:
        """Assert CSVFormat."""
        csv_format = get_csv_format(
            self.CONFIG,
            self.CSV_FORMAT,
        )
        mappings = get_config_value(self.CONFIG, "mappings")
        skip_descriptions = get_config_value(self.CONFIG, "skip_descriptions")
        skip_currencies = get_config_value(self.CONFIG, "skip_currencies")

        trans = CSVParser(
            csv_format,
            mappings,
            skip_descriptions,
            skip_currencies,
        ).get_gnucash_transactions(self.get_data_files(filename)[0])
        assert len(trans) == total

        trans = [t for t in trans if t.account == ""]
        assert len(trans) <= total * self.BAD_TRANS_RATIO


class PrivateConfig:
    """Class for private config."""

    CONFIG = Path(__file__).parent / "private/config.json"
    TYPE = "private"


class PublicConfig:
    """Class for public config."""

    CONFIG = Path(__file__).parent / "public/config.json"
    TYPE = "public"
