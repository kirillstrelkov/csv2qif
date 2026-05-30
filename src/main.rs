use anyhow::Result;
use clap::{command, Parser, ValueEnum};
use csv2qif::{csv2qif, get_config, Input};
use fern::colors::{Color, ColoredLevelConfig};
use log::{debug, info, LevelFilter};
use std::fs;
use std::{fmt, path::PathBuf};

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
    #[arg(short, long, default_value_t = LogLevel::Info)]
    log_level: LogLevel,
}

#[derive(ValueEnum, Clone, Debug)]
enum LogLevel {
    Error,
    Warn,
    Info,
    Debug,
    Trace,
}

impl From<LogLevel> for LevelFilter {
    fn from(level: LogLevel) -> Self {
        match level {
            LogLevel::Error => LevelFilter::Error,
            LogLevel::Warn => LevelFilter::Warn,
            LogLevel::Info => LevelFilter::Info,
            LogLevel::Debug => LevelFilter::Debug,
            LogLevel::Trace => LevelFilter::Trace,
        }
    }
}
impl fmt::Display for LogLevel {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            LogLevel::Error => write!(f, "error"),
            LogLevel::Warn => write!(f, "warn"),
            LogLevel::Info => write!(f, "info"),
            LogLevel::Debug => write!(f, "debug"),
            LogLevel::Trace => write!(f, "trace"),
        }
    }
}

fn setup_logger(log_level: LevelFilter) -> Result<()> {
    let colors = ColoredLevelConfig::new()
        .error(Color::Red)
        .warn(Color::Yellow)
        .info(Color::Green)
        .debug(Color::Cyan)
        .trace(Color::Magenta);

    fern::Dispatch::new()
        .format(move |out, message, record| {
            out.finish(format_args!(
                "[{}][{}][{}] {}",
                chrono::Local::now().format("%Y-%m-%d %H:%M:%S"),
                record.target(),
                colors.color(record.level()),
                message
            ))
        })
        .level(log::LevelFilter::Warn) // Set the default level
        .level_for(module_path!(), log_level) // Set the default level
        .chain(std::io::stdout())
        .apply()?;

    Ok(())
}

fn main() -> Result<()> {
    let args = Args::parse();

    setup_logger(args.log_level.into())?;

    debug!(
        "Using input {} and config {}",
        args.input.display(),
        args.config.display()
    );

    let input = Input::Path(args.input);
    let config = get_config(args.config.as_path())?;

    let qif_content = csv2qif(&input, &config, &args.format, &args.account)?;

    info!("Creating file {}", args.output.display());

    fs::write(args.output, qif_content)?;
    Ok(())
}
