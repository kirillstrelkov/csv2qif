"""Banks tests."""
from csv2qif import csv2qif
from tests.helper import DataTestCase, PublicConfig


class QIFTransactionsTest(DataTestCase, PublicConfig):
    """QIF transactions test."""

    TYPE = "public"
    GNUCASH_ALIAS = "bank_a"

    def test_account_name(self) -> None:
        """Check account name."""
        expected = """!Account
NAssets:Current Assets:Bank A
^
!Type:Bank
D29.12.2015
T-42.02
PAmerican whole magazine truth stop whose ABD
LImbalance-EUR
^"""
        input_ = """"Client account";"Row type";"Date";"Beneficiary/Payer";"Details";"Amount";"Currency";"Debit/Credit";"Transfer reference";"Transaction type";"Reference number";"Document number";
"GB75GZUL15871484185839";"20";"29.12.2015";"ABD";"American whole magazine truth stop whose";"42,02";"EUR";"D";"GB75GZUL15871484185839";"MK";"GB75GZUL15871484185839";"1758";"""
        actual = csv2qif(input_, self.CONFIG, "Bank A", "bank_a")
        assert actual == expected

    def test_bank_a(self) -> None:
        """Check bank A."""
        self.assert_qif_trans(12, 6, filename="bank_a_2016.csv", csv_format="Bank A")

    def test_bank_b(self) -> None:
        """Check bank B."""
        self.assert_qif_trans(12, 9, filename="bank_b_2019.csv", csv_format="Bank B")
