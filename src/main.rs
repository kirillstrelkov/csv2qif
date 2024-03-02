use csv2qif::{csv2qif, get_config, Input};
use std::{fs, path::PathBuf};

use clap::{command, Parser};

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
}

fn main() -> std::io::Result<()> {
    let args = Args::parse();

    let input = Input::Path(args.input);
    let config = get_config(args.config.as_path())?;
    let qif_content = csv2qif(&input, &config, &args.format, &args.account)?;
    fs::write(args.output, qif_content)?;
    Ok(())
}
