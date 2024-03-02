use csv2qif::{get_input_files, Input};

use crate::helper::{TestType, _assert_qif_trans, get_data_folder};

pub fn assert_qif_trans(
    expected_nr_qifs: usize,
    expected_nr_imbalanced: usize,
    filename: Option<&str>,
    format: &str,
    qif_account_key: &str,
) {
    _assert_qif_trans(
        expected_nr_qifs,
        expected_nr_imbalanced,
        filename,
        format,
        qif_account_key,
        TestType::PUBLIC,
    );
}

#[test]
fn test_get_public_input_files() {
    let data_folder = get_data_folder(TestType::PUBLIC);
    let files = get_input_files(&Input::Path(data_folder));
    assert_eq!(files.len(), 2)
}
