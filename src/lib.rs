use core::result::Result as CoreResult;
use csv::ReaderBuilder;
use glob::glob;
use lazy_static::lazy_static;
use log::warn;
use rayon::prelude::*;
use regex::Regex;
use serde::{Deserialize, Deserializer, Serialize};
use std::io::Read;
use std::io::Result;
use std::path::Path;
use std::{collections::HashMap, fs::File, path::PathBuf};
use std::{fmt, fs};

lazy_static! {
    static ref RE_WRONG_DESC: Regex = Regex::new(r"[;,\s]+").unwrap();
    static ref RE_QUOTES: Regex = Regex::new(r#"[\"']+"#).unwrap();
    static ref RE_NUMBER: Regex = Regex::new(r"[^\d,.\-]+").unwrap();
    static ref RE_COMMA_DOT: Regex = Regex::new("[,.]").unwrap();
    static ref RE_WORD: Regex = Regex::new(r"\w+").unwrap();
}

#[derive(Debug)]
pub struct DescPattern {
    string: String,
    regex: Option<Regex>,
}

fn match_description(description: &str, pattern: &DescPattern) -> bool {
    if description.contains(&pattern.string) {
        return true;
    }

    match pattern.regex {
        Some(ref regex) => regex.is_match(description),
        None => false,
    }
}

fn fix_description(descs: Vec<&str>) -> String {
    let description = descs.join(" ");
    let description = RE_QUOTES.replace_all(&description, "").into_owned();
    RE_WRONG_DESC.replace_all(&description, " ").into_owned()
}

fn map_string_to_regexps(strings: &[String]) -> Vec<DescPattern> {
    strings
        .iter()
        .map(|s| {
            let pattern: String = format!("(?i){s}");
            let re = match Regex::new(&pattern) {
                Ok(re) => Some(re),
                Err(_) => None,
            };
            DescPattern {
                string: s.to_string(),
                regex: re,
            }
        })
        .collect()
}

fn deserialize_description_vec<'de, D>(deserializer: D) -> CoreResult<Vec<DescPattern>, D::Error>
where
    D: Deserializer<'de>,
{
    let old_vec = Vec::<String>::deserialize(deserializer).unwrap();
    Ok(map_string_to_regexps(&old_vec))
}

fn deserialize_description_map<'de, D>(
    deserializer: D,
) -> CoreResult<HashMap<String, Vec<DescPattern>>, D::Error>
where
    D: Deserializer<'de>,
{
    let old_mappings = HashMap::<String, Vec<String>>::deserialize(deserializer).unwrap();
    let mut new_mappings = HashMap::<String, Vec<DescPattern>>::new();

    for (key, values) in old_mappings {
        let regex_vec = map_string_to_regexps(&values);
        new_mappings.insert(key, regex_vec);
    }

    Ok(new_mappings)
}

#[derive(Deserialize, Debug)]
pub struct Config {
    pub formats: Vec<Format>,
    pub qif_aliases: HashMap<String, String>,
    #[serde(deserialize_with = "deserialize_description_vec")]
    pub skip_descriptions: Vec<DescPattern>,
    #[serde(deserialize_with = "deserialize_description_map")]
    pub mappings: HashMap<String, Vec<DescPattern>>,
}

impl Config {
    pub fn get_account(&self, description: &str) -> String {
        for (account, descs) in &self.mappings {
            for desc in descs {
                if match_description(description, desc) {
                    return account.to_string();
                }
            }
        }

        "Imbalance-EUR".to_string()
    }

    pub fn get_format(&self, name: &str) -> Result<&Format> {
        if let Some(found_format) = self.formats.iter().find(|&f| f.name == name) {
            Ok(found_format)
        } else {
            panic!("Failed for find format for {name}");
        }
    }
}

#[derive(Serialize, Deserialize, Debug)]
pub struct Format {
    name: String,
    delimiter: Vec<String>,
    description: Vec<String>,
    date: Vec<String>,
}

#[derive(Debug)]
pub enum Input {
    String(String),
    Path(PathBuf),
}

#[derive(Debug)]
pub struct Transaction {
    date: String,
    description: String,
    account: String,
    increase: f64,
    decrease: f64,
}

impl Transaction {
    pub fn from(
        config: &Config,
        format: &Format,
        data: &HashMap<String, &str>,
    ) -> Option<Transaction> {
        let mut date = "".to_string();
        for date_key in &format.date {
            if let Some(&date_value) = data.get(date_key) {
                date = date_value.to_string();
                break;
            }
        }
        let amount: f64 = match data.get("amount") {
            Some(value) => parse_float(value).unwrap_or(0.0),
            None => 0.0,
        };
        let mut increase = 0.0;
        let mut decrease = 0.0;

        match data.get("debit_credit") {
            Some(&value) => {
                if value == "K" {
                    increase = amount;
                } else {
                    decrease = amount.abs();
                }
            }
            None => {
                if amount >= 0.0 {
                    increase = amount;
                } else {
                    decrease = amount.abs();
                }
            }
        }

        let descs: Vec<&str> = format
            .description
            .iter()
            .filter_map(|desc| data.get(desc))
            .copied()
            .collect();
        let description = fix_description(descs);
        let account = config.get_account(&description);

        for skip_desc in &config.skip_descriptions {
            if match_description(&description, skip_desc) {
                return None;
            }
        }

        Some(Transaction {
            date,
            description,
            account,
            increase,
            decrease,
        })
    }
}

#[derive(Debug)]
pub struct QifTransaction {
    pub date: String,
    pub amount: f64,
    pub description: String,
    pub account: String,
}

impl fmt::Display for QifTransaction {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let date: &String = &self.date;
        let amount = self.amount;
        let description = &self.description;
        let account = &self.account;
        let string = format!(
            r#"!Type:Bank
D{date}
T{amount}
P{description}
L{account}
^"#
        );
        write!(f, "{}", string)
    }
}

impl QifTransaction {
    pub fn from(transaction: &Transaction) -> QifTransaction {
        QifTransaction {
            date: transaction.date.to_owned(),
            amount: if transaction.increase > 0.0 {
                transaction.increase
            } else {
                -transaction.decrease
            },
            description: transaction.description.to_owned(),
            account: transaction.account.to_string(),
        }
    }
}

pub fn get_config(path: &Path) -> Result<Config> {
    let mut file = File::open(path)?;

    let mut contents = String::new();
    file.read_to_string(&mut contents)?;

    Ok(serde_json::from_str(&contents)?)
}

pub fn get_qif_trans_from_csv(
    files: &Vec<PathBuf>,
    config: &Config,
    format: &str,
    account_from: &str,
) -> Result<Vec<QifTransaction>> {
    let format = config.get_format(format)?;
    let trans = files
        .into_par_iter()
        .flat_map(|file| {
            let input = Input::Path(file.to_owned());
            match get_qif_trans(&input, config, format, account_from) {
                Ok(trans) => trans,
                Err(_err) => {
                    warn!("Failed to parse file {:?}", file);
                    vec![]
                }
            }
        })
        .collect();
    Ok(trans)
}

fn parse_float(text: &str) -> Option<f64> {
    // leave only numbers, comma and dot
    let mut text = RE_NUMBER.replace_all(text, "").to_string();

    if RE_COMMA_DOT.find_iter(&text).count() == 2 {
        text = RE_COMMA_DOT.replace(&text, "").to_string();
    }
    text = RE_COMMA_DOT.replace(&text, ".").to_string();

    match text.parse() {
        Ok(value) => Some(value),
        Err(_) => None,
    }
}

fn get_header_name(header: &str) -> String {
    let words: Vec<&str> = RE_WORD.find_iter(header).map(|mat| mat.as_str()).collect();
    words.join("_").to_lowercase()
}

pub fn get_files(path: &Path) -> Vec<PathBuf> {
    let path = path.to_str().unwrap();
    let pattern = format!("{path}/**/*.csv");
    match glob(&pattern) {
        Ok(paths) => paths.into_iter().filter_map(|r| r.ok()).collect(),
        Err(_) => vec![],
    }
}

pub fn get_input_files(input: &Input) -> Vec<PathBuf> {
    match input {
        Input::Path(path) => {
            if path.is_dir() {
                get_files(path).into_iter().collect()
            } else {
                vec![path.to_owned()]
            }
        }
        _ => {
            vec![]
        }
    }
}

fn get_qif_trans_from_string_with_delimiter(
    context: &String,
    config: &Config,
    delimiter: u8,
    format: &Format,
    account_from: &str,
) -> Vec<QifTransaction> {
    let mut rdr = ReaderBuilder::new()
        .delimiter(delimiter)
        .from_reader(context.as_bytes());

    let mut data = vec![];
    let headers = rdr.headers().unwrap().clone();
    if headers.len() <= 1 {
        return vec![];
    }

    let headers = headers.into_iter().map(get_header_name);
    for record in rdr.records() {
        let x = match record {
            Ok(value) => value,
            Err(err) => panic!("Failed to parse: {err}"),
        };
        // TODO: improve by removing cloning
        let row = headers
            .clone()
            .zip(x.iter())
            .collect::<HashMap<String, &str>>();
        if let Some(transaction) = Transaction::from(config, format, &row) {
            if account_from == transaction.account {
                warn!("SKIP: Found transaction with same account: {transaction:?}");
            }
            data.push(transaction);
        }
    }

    data.into_iter().map(|t| QifTransaction::from(&t)).collect()
}

fn get_qif_trans_from_string(
    context: &String,
    config: &Config,
    format: &Format,
    account_from: &str,
) -> Vec<QifTransaction> {
    for delimiter in &format.delimiter {
        let res = get_qif_trans_from_string_with_delimiter(
            context,
            config,
            delimiter.as_bytes()[0],
            format,
            account_from,
        );
        if !res.is_empty() {
            return res;
        }
    }

    get_qif_trans_from_string_with_delimiter(context, config, b'\t', format, account_from)
}

fn get_qif_trans(
    input: &Input,
    config: &Config,
    format: &Format,
    account_from: &str,
) -> Result<Vec<QifTransaction>> {
    Ok(match input {
        Input::String(content) => get_qif_trans_from_string(content, config, format, account_from),
        Input::Path(path) => get_input_files(&Input::Path(path.to_owned()))
            .into_iter()
            .flat_map(|p| {
                get_qif_trans_from_string(
                    &fs::read_to_string(p).unwrap(),
                    config,
                    format,
                    account_from,
                )
            })
            .collect(),
    })
}

fn qif_trans_to_string(trans: &[QifTransaction], qif_account_key: &str) -> String {
    let trans = trans
        .iter()
        .map(|t| t.to_string())
        .collect::<Vec<String>>()
        .join("\n");
    format!(
        r#"!Account
N{qif_account_key}
^
{trans}"#
    )
}

pub fn csv2qif(input: &Input, config: &Config, format: &str, account_key: &str) -> Result<String> {
    let qif_account_key = &config.qif_aliases[account_key];
    let format = config.get_format(format)?;
    let qif_trans = get_qif_trans(input, config, format, qif_account_key)?;

    Ok(qif_trans_to_string(&qif_trans, qif_account_key))
}

#[cfg(test)]
mod tests {

    mod parse_float {
        use crate::parse_float;

        #[test]
        fn two_decimals() {
            let expected = Some(12345.67);
            // dot as decimal separator
            assert_eq!(parse_float("12,345.67"), expected);
            assert_eq!(parse_float("12 345.67"), expected);
            assert_eq!(parse_float("12345.67"), expected);

            // comma as decimal separator
            assert_eq!(parse_float("12.345,67"), expected);
            assert_eq!(parse_float("12 345,67"), expected);
            assert_eq!(parse_float("12345,67"), expected);
        }

        #[test]
        fn one_decimal() {
            let expected = Some(12345.60);
            // dot as decimal separator
            assert_eq!(parse_float("12,345.6"), expected);
            assert_eq!(parse_float("12 345.6"), expected);
            assert_eq!(parse_float("12345.6"), expected);

            // comma as decimal separator
            assert_eq!(parse_float("12.345,6"), expected);
            assert_eq!(parse_float("12 345,6"), expected);
            assert_eq!(parse_float("12345,6"), expected);
        }

        #[test]
        fn no_decimals() {
            let expected = Some(12345.00);
            assert_eq!(parse_float("12 345"), expected);
            assert_eq!(parse_float("12345"), expected);
        }

        #[test]
        fn no_thousands() {
            let expected = Some(12.345);
            assert_eq!(parse_float("12,345"), expected);
            assert_eq!(parse_float("12.345"), expected);
        }

        #[test]
        fn negative() {
            {
                let expected = Some(-12345.67);
                // dot as decimal separator
                assert_eq!(parse_float("-12,345.67"), expected);
                assert_eq!(parse_float("-12 345.67"), expected);
                assert_eq!(parse_float("-12345.67"), expected);

                // comma as decimal separator
                assert_eq!(parse_float("-12.345,67"), expected);
                assert_eq!(parse_float("-12 345,67"), expected);
                assert_eq!(parse_float("-12345,67"), expected);
            }

            {
                let expected = Some(-12345.00);
                assert_eq!(parse_float("-12 345"), expected);
                assert_eq!(parse_float("-12345"), expected);
            }
        }
    }

    mod get_header_name {
        use crate::get_header_name;

        #[test]
        fn spaces() {
            assert_eq!(get_header_name("a B c"), "a_b_c");
        }

        #[test]
        fn special_chars() {
            assert_eq!(get_header_name("a,. 'B! c'"), "a_b_c");
        }
    }

    mod fix_description {
        use crate::fix_description;

        #[test]
        fn simple() {
            assert_eq!(fix_description(vec!["234", "abc"]), "234 abc");
            assert_eq!(fix_description(vec!["234  ", "\tabc"]), "234 abc");
            assert_eq!(
                fix_description(vec!["'234'", "'abc'", "'34'"]),
                "234 abc 34"
            );
        }
    }
}
