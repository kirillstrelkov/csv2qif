from tests.helper import DataTestCase, PublicConfig
from csv2qif import csv2qif


class QIFTransactionsTest(DataTestCase, PublicConfig):
    TYPE = "public"
    GNUCASH_ALIAS = "bank_a"

    def test_account_name(self):
        expected = """!Account
NAssets:Current Assets:Bank A
^
!Type:Bank
D29.12.2015
T-42.02
PAmerican whole magazine truth stop whose ABD
LImbalance-EUR
^"""
        input = """"Client account";"Row type";"Date";"Beneficiary/Payer";"Details";"Amount";"Currency";"Debit/Credit";"Transfer reference";"Transaction type";"Reference number";"Document number";
"GB75GZUL15871484185839";"20";"29.12.2015";"ABD";"American whole magazine truth stop whose";"42,02";"EUR";"D";"GB75GZUL15871484185839";"MK";"GB75GZUL15871484185839";"1758";"""
        actual = csv2qif(input, self.CONFIG, "Bank A", "bank_a")
        assert actual == expected

    def test_bank_a(self):
        self.assert_qif_trans("bank_a_2016.csv", 12, 6, csv_format="Bank A")

    def test_bank_b(self):
        self.assert_qif_trans("bank_b_2019.csv", 12, 9, csv_format="Bank B")
