use anyhow::{bail, Context, Result};
use csv::ReaderBuilder;
use glob::glob;
use lazy_static::lazy_static;
use log::{debug, info, trace, warn};
use rayon::prelude::*;
use regex::Regex;
use serde::{Deserialize, Deserializer, Serialize};
use std::collections::HashMap;
use std::fmt;
use std::fs::{self, File};
use std::io::Read;
use std::path::{Path, PathBuf};

lazy_static! {
    static ref RE_WRONG_DESC: Regex = Regex::new(r"[;,\s]+").unwrap();
    static ref RE_QUOTES: Regex = Regex::new(r#"[\"']+"#).unwrap();
    static ref RE_NUMBER: Regex = Regex::new(r"[^\d,.\-]+").unwrap();
    static ref RE_COMMA_DOT: Regex = Regex::new("[,.]").unwrap();
    static ref RE_WORD: Regex = Regex::new(r"\w+").unwrap();
}

#[derive(Debug)]
pub struct DescPattern {
    pub string: String,
    regex: Option<Regex>,
}

pub fn match_description(description: &str, pattern: &DescPattern) -> bool {
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
            let pattern = format!("(?i){s}");
            let re = Regex::new(&pattern).ok();
            DescPattern {
                string: s.to_string(),
                regex: re,
            }
        })
        .collect()
}

fn deserialize_description_vec<'de, D>(deserializer: D) -> Result<Vec<DescPattern>, D::Error>
where
    D: Deserializer<'de>,
{
    let old_vec = Vec::<String>::deserialize(deserializer)?;
    Ok(map_string_to_regexps(&old_vec))
}

fn deserialize_description_list<'de, D>(
    deserializer: D,
) -> Result<Vec<(String, Vec<DescPattern>)>, D::Error>
where
    D: Deserializer<'de>,
{
    let old_mappings = Vec::<(String, Vec<String>)>::deserialize(deserializer)?;
    let new_mappings = old_mappings
        .into_iter()
        .map(|(key, values)| (key, map_string_to_regexps(&values)))
        .collect();

    Ok(new_mappings)
}

#[derive(Deserialize, Debug)]
pub struct Config {
    pub formats: Vec<Format>,
    pub qif_aliases: HashMap<String, String>,
    #[serde(deserialize_with = "deserialize_description_vec")]
    pub skip_descriptions: Vec<DescPattern>,
    #[serde(deserialize_with = "deserialize_description_list")]
    pub mappings: Vec<(String, Vec<DescPattern>)>,
}

impl Config {
    pub fn get_account(&self, description: &str) -> &str {
        for (account, descs) in &self.mappings {
            for desc in descs {
                if match_description(description, desc) {
                    trace!(
                        "Mapped description '{}' to account '{}'",
                        description,
                        account
                    );
                    return account;
                }
            }
        }
        warn!(
            "No mapping found for description '{}', falling back to 'Imbalance-EUR'",
            description
        );
        "Imbalance-EUR"
    }

    pub fn get_format(&self, name: &str) -> Result<&Format> {
        self.formats
            .iter()
            .find(|f| f.name == name)
            .with_context(|| format!("Failed to find format config for '{name}'"))
    }
}

#[derive(Serialize, Deserialize, Debug)]
pub struct Format {
    name: String,
    delimiter: Vec<String>,
    description: Vec<String>,
    date: Vec<String>,
    #[serde(default = "default_format_amount")]
    amount: Vec<String>,
}

fn default_format_amount() -> Vec<String> {
    vec![String::from("amount")]
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
    pub fn is_valid(&self) -> bool {
        !self.date.is_empty()
            && !self.description.is_empty()
            && (self.increase != 0.0 || self.decrease != 0.0)
    }

    pub fn from(
        config: &Config,
        format: &Format,
        data: &HashMap<&str, &str>, // Changed to completely zero-allocation keys
    ) -> Option<Transaction> {
        let mut date = String::new();
        for date_key in &format.date {
            if let Some(&date_value) = data.get(date_key.as_str()) {
                date = date_value.to_string();
                break;
            }
        }

        let mut amount: f64 = 0.0;
        for amount_key in &format.amount {
            if let Some(&value) = data.get(amount_key.as_str()) {
                amount = parse_float(value).unwrap_or(0.0);
                break;
            }
        }

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
            .filter_map(|desc| data.get(desc.as_str()))
            .copied()
            .collect();

        let description = fix_description(descs);
        let account = config.get_account(&description).to_string();

        for skip_desc in &config.skip_descriptions {
            if match_description(&description, skip_desc) {
                trace!(
                    "Skipping transaction matching pattern '{}': '{}'",
                    skip_desc.string,
                    description
                );
                return None;
            }
        }

        let tran = Transaction {
            date,
            description,
            account,
            increase,
            decrease,
        };

        if !tran.is_valid() {
            warn!("Failed to process: transaction is invalid (empty date/description or zero amount). data: {data:?} -> processed transaction: {tran:?}");
            return None;
        }

        Some(tran)
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
        write!(
            f,
            "!Type:Bank\nD{}\nT{}\nP{}\nL{}\n^",
            self.date, self.amount, self.description, self.account
        )
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
            account: transaction.account.clone(),
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
    files: &[PathBuf],
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
                Err(err) => {
                    warn!("Failed to parse file {}: {:?}", file.display(), err);
                    vec![]
                }
            }
        })
        .collect();
    Ok(trans)
}

fn parse_float(text: &str) -> Option<f64> {
    let mut text = RE_NUMBER.replace_all(text, "").to_string();

    if RE_COMMA_DOT.find_iter(&text).count() == 2 {
        text = RE_COMMA_DOT.replace(&text, "").to_string();
    }
    text = RE_COMMA_DOT.replace(&text, ".").to_string();

    text.parse().ok()
}

fn get_header_name(header: &str) -> String {
    let words: Vec<&str> = RE_WORD.find_iter(header).map(|mat| mat.as_str()).collect();
    words.join("_").to_lowercase()
}

pub fn get_files(path: &Path) -> Vec<PathBuf> {
    let pattern = path.join("**").join("*.csv");
    let pattern_str = match pattern.to_str() {
        Some(s) => s,
        None => return vec![],
    };

    match glob(pattern_str) {
        Ok(paths) => paths.filter_map(Result::ok).collect(),
        Err(_) => vec![],
    }
}

pub fn get_input_files(input: &Input) -> Vec<PathBuf> {
    match input {
        Input::Path(path) => {
            if path.is_dir() {
                get_files(path)
            } else {
                vec![path.to_owned()]
            }
        }
        _ => vec![],
    }
}

fn get_qif_trans_from_string_with_delimiter(
    context: &str,
    config: &Config,
    delimiter: u8,
    format: &Format,
    account_from: &str,
) -> Vec<QifTransaction> {
    let mut rdr = ReaderBuilder::new()
        .delimiter(delimiter)
        .from_reader(context.as_bytes());

    let mut data = vec![];

    let raw_headers = match rdr.headers() {
        Ok(h) => h.clone(),
        Err(err) => {
            trace!(
                "Failed to read CSV headers for delimiter (byte {}): {:?}",
                delimiter,
                err
            );
            return vec![];
        }
    };

    if raw_headers.len() <= 1 {
        trace!(
            "CSV has too few columns (headers count: {}) for delimiter (byte {})",
            raw_headers.len(),
            delimiter
        );
        return vec![];
    }

    // Process converted header names once here out-of-the-loop!
    let headers: Vec<String> = raw_headers.iter().map(get_header_name).collect();

    for record in rdr.records().flatten() {
        let row = headers
            .iter()
            .map(String::as_str)
            .zip(record.iter())
            .collect::<HashMap<&str, &str>>();

        if let Some(transaction) = Transaction::from(config, format, &row) {
            if account_from == transaction.account {
                warn!("Transaction has the same source and destination account (self-transfer): {transaction:?}");
            }
            data.push(transaction);
        }
    }

    data.into_iter().map(|t| QifTransaction::from(&t)).collect()
}

fn get_qif_trans_from_string(
    context: &str,
    config: &Config,
    format: &Format,
    account_from: &str,
) -> Result<Vec<QifTransaction>> {
    if format.delimiter.is_empty() {
        bail!("Format '{}' has no delimiters configured.", format.name);
    }

    for delimiter in &format.delimiter {
        if let Some(delim_byte) = delimiter.as_bytes().first() {
            trace!(
                "Trying delimiter '{}' for format '{}'",
                delimiter,
                format.name
            );
            let res = get_qif_trans_from_string_with_delimiter(
                context,
                config,
                *delim_byte,
                format,
                account_from,
            );

            if !res.is_empty() {
                trace!(
                    "Successfully parsed {} transactions using delimiter '{}' for format '{}'",
                    res.len(),
                    delimiter,
                    format.name
                );
                return Ok(res);
            } else {
                trace!(
                    "Delimiter '{}' for format '{}' yielded 0 transactions",
                    delimiter,
                    format.name
                );
            }
        } else {
            bail!(
                "Format '{}' contains an empty string as a delimiter.",
                format.name
            );
        }
    }

    bail!(
        "Failed to parse any transactions using the configured delimiters {:?} for format '{}'.",
        format.delimiter,
        format.name
    );
}

fn get_qif_trans(
    input: &Input,
    config: &Config,
    format: &Format,
    account_from: &str,
) -> Result<Vec<QifTransaction>> {
    match input {
        Input::String(content) => get_qif_trans_from_string(content, config, format, account_from),
        Input::Path(path) => get_input_files(&Input::Path(path.to_owned()))
            .into_iter()
            .map(|p| {
                trace!("Reading {}", p.display());
                let content = fs::read_to_string(&p).with_context(|| {
                    format!("file or folder \"{}\" does not exist", p.display())
                })?;

                let trans = get_qif_trans_from_string(&content, config, format, account_from)?;
                debug!(
                    "Parsed {} transactions from file '{}'",
                    trans.len(),
                    p.display()
                );
                Ok(trans)
            })
            .collect::<Result<Vec<Vec<QifTransaction>>>>()
            .map(|nested| nested.into_iter().flatten().collect()),
    }
}

fn qif_trans_to_string(trans: &[QifTransaction], qif_account_key: &str) -> String {
    let trans = trans
        .iter()
        .map(|t| t.to_string())
        .collect::<Vec<String>>()
        .join("\n");
    format!("!Account\nN{qif_account_key}\n^\n{trans}")
}

pub fn csv2qif(input: &Input, config: &Config, format: &str, account_key: &str) -> Result<String> {
    let qif_account_key = match config.qif_aliases.get(account_key) {
        Some(k) => k,
        None => bail!("Missing QIF alias mapping for account key: '{account_key}'"),
    };
    let format = config.get_format(format)?;

    info!("Using '{qif_account_key}' and {format:?} to process {input:?}");

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
