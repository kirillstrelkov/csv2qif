use anyhow::Result;
use clap::{command, Parser, ValueEnum};
use csv2qif::{csv2qif, get_config, Input};
use log::{debug, info};
use std::fs;
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
struct Args {
    /// Path to input CSV file
    input: PathBuf,

    /// Path to output QIF file
    output: PathBuf,

    /// Format to be used from config file
    #[arg(short, long)]
    format: String,

    /// Key in qif_aliases which is used as account name in QIF file
    #[arg(short, long)]
    account: String,

    /// Path to config file
    #[arg(short, long)]
    config: PathBuf,

    /// Log level
    #[arg(short = 'l', long = "log-level", value_enum, default_value = "info")]
    log_level: LogLevel,
}

#[derive(ValueEnum, Clone, Copy, Debug, PartialEq, Eq)]
enum LogLevel {
    Error,
    Warn,
    Info,
    Debug,
    Trace,
}

fn init_logger(level: LogLevel) {
    let level_str = format!("{:?}", level).to_lowercase();

    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or(&level_str))
        .target(env_logger::Target::Stderr)
        .init();
}

fn main() -> Result<()> {
    let args = Args::parse();

    init_logger(args.log_level);

    debug!(
        "Processing data from '{}' with config '{}'",
        args.input.display(),
        args.config.display()
    );

    let input = Input::Path(args.input);
    let config = get_config(args.config.as_path())?;

    let qif_content = csv2qif(&input, &config, &args.format, &args.account)?;

    info!("Output was created {}", args.output.display());

    fs::write(args.output, qif_content)?;
    Ok(())
}
