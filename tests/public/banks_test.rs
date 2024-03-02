use crate::helper::get_test_config;
use crate::helper::TestType;
use csv2qif::csv2qif;
use csv2qif::Input;

use super::helper::assert_qif_trans;

#[test]
fn test_account_name() {
    let expected = r#"!Account
NAssets:Current Assets:Bank A
^
!Type:Bank
D29.12.2015
T-42.02
PAmerican whole magazine truth stop whose ABD
LImbalance-EUR
^"#;

    let input_ = Input::String(r#"Client account";"Row type";"Date";"Beneficiary/Payer";"Details";"Amount";"Currency";"Debit/Credit";"Transfer reference";"Transaction type";"Reference number";"Document number";
"GB75GZUL15871484185839";"20";"29.12.2015";"ABD";"American whole magazine truth stop whose";"42,02";"EUR";"D";"GB75GZUL15871484185839";"MK";"GB75GZUL15871484185839";"1758";"#.to_string());
    let config = get_test_config(TestType::PUBLIC);
    let actual = csv2qif(&input_, &config, "Bank A", "bank_a").unwrap();
    assert_eq!(&actual, expected);
}

#[test]
fn test_bank_a() {
    assert_qif_trans(12, 6, Some("bank_a_2016.csv"), "Bank A", "bank_a");
}

#[test]
fn test_bank_b() {
    assert_qif_trans(12, 9, Some("bank_b_2019.csv"), "Bank B", "bank_a");
}
