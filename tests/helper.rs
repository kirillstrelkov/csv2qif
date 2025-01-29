use std::path::PathBuf;

use csv2qif::{get_config, get_qif_trans_from_csv, Config, QifTransaction};
use glob::{glob_with, MatchOptions};
use log::error;
use regex::Regex;

pub enum TestType {}

impl TestType {
    #[allow(dead_code)]
    pub const PRIVATE: &'static str = "private";
    pub const PUBLIC: &'static str = "public";
}

fn get_public_or_private_folder(test_type: &str) -> PathBuf {
    let path = file!();
    let path = PathBuf::from(path);
    let test_folder = path.parent().unwrap();
    assert!(test_folder.exists());
    PathBuf::from(test_folder).join(test_type)
}

pub fn get_data_folder(test_type: &str) -> PathBuf {
    let data_folder = get_public_or_private_folder(test_type).join("data");
    assert!(data_folder.exists());
    data_folder
}

pub fn get_test_config(test_type: &str) -> Config {
    let config_path = get_public_or_private_folder(test_type).join("config.json");
    assert!(config_path.exists());

    get_config(config_path.as_path()).unwrap()
}

pub fn get_data_files(filename: Option<&str>, test_type: &str) -> Vec<PathBuf> {
    let folder = get_data_folder(test_type);
    let data_folder = folder.to_str().unwrap();
    let pattern = match filename {
        Some(value) => format!("{data_folder}/**/{value}"),
        None => format!("{data_folder}/**/*.csv"),
    };
    let options = MatchOptions::default();
    match glob_with(&pattern, options) {
        Ok(paths) => paths.into_iter().filter_map(|r| r.ok()).collect(),
        Err(_) => vec![],
    }
}

fn assert_imbalanced_and_counts(
    trans: &Vec<QifTransaction>,
    expected_nr_imbalanced: usize,
    expected_nr_qifs: usize,
) {
    let mut imbalanced: Vec<&QifTransaction> = trans
        .iter()
        .filter(|t| t.account.to_lowercase().contains("imbalance"))
        .collect();

    imbalanced.sort_by_key(|&t| {
        t.date
            .split('.')
            .map(|s| s.parse::<i32>().unwrap_or(0))
            .rev()
            .collect::<Vec<i32>>()
    });

    if imbalanced.len() != expected_nr_imbalanced {
        for &t in &imbalanced {
            error!(
                "{}\t{}\t{},\t{}",
                t.date, t.amount, t.description, t.account
            );
        }

        let mut descs = imbalanced
            .iter()
            .map(|&t| format!("{},{},{}", t.description.to_lowercase(), t.date, t.amount))
            .collect::<Vec<String>>();
        descs.sort();
        let msg = descs.join("\n");
        error!("Sorted by descriptions:\n{}", msg);
    }

    assert_eq!(imbalanced.len(), expected_nr_imbalanced);
    assert_eq!(trans.len(), expected_nr_qifs);
}

fn assert_descriptions(trans: &Vec<QifTransaction>) {
    let regexp = Regex::new(r"\s{2,}").unwrap();
    for tran in trans {
        for char in ['"', '\''] {
            assert!(!tran.description.starts_with(char));
            assert!(!tran.description.ends_with(char));
        }

        assert!(
            regexp.find(&tran.description).is_none(),
            "Found spaces in '{}'",
            tran.description
        );
    }
}
pub fn get_bank_transactions(
    filename: Option<&str>,
    format: &str,
    qif_account_key: &str,
    test_type: &str,
) -> Vec<QifTransaction> {
    let config = get_test_config(test_type);
    let qif_account_key = config.qif_aliases.get(qif_account_key).unwrap();
    let files = get_data_files(filename, test_type);

    get_qif_trans_from_csv(&files, &config, &format, qif_account_key).unwrap()
}

pub fn assert_qif_trans(
    expected_nr_qifs: usize,
    expected_nr_imbalanced: usize,
    filename: Option<&str>,
    format: &str,
    qif_account_key: &str,
    test_type: &str,
) {
    let trans = get_bank_transactions(filename, format, qif_account_key, test_type);
    assert_imbalanced_and_counts(&trans, expected_nr_imbalanced, expected_nr_qifs);
    assert_descriptions(&trans);
}
