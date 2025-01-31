# CSV2QIF

Application which converts CSV format to QIF and categarize transactions based on config file.

Example usage with [config from tests](tests/public/config.json):

```bash
csv2qif /tmp/my_bank.csv /tmp/out.qif -c tests/public/config.json -f 'Bank A' -a bank_a
```

## Limitation with old version

- `encoding` is not supported in config file. It is expected that all files are saved in **UTF8**.
- output file can contain duplicates

Old version can be found https://github.com/kirillstrelkov/csv2qif/tree/main_py

## Config file

Config file contains information about how to parse transactions from CSV file and how to format transaction in QIF file. See [test config](tests/public/config.json) for example.

Here is overview of keys in config file:

| key               | comment                                                                                                                |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------- |
| formats           | config for CSV file from one bank                                                                                      |
| qif_aliases       | QIF account name, shortcut which can be used with `-a` flag                                                            |
| skip_descriptions | Transactions which contain these text or match regexp will be skipped                                                  |
| mappings          | QIF account name and list of texts/pattern that will be matched transactions to this account. **NOTE:** order matters. |

Config example for one bank:

```json
{
  "formats": [
    {
      "name": "Bank A",
      "delimiter": [";"],
      "description": ["details", "beneficiary_payer"],
      "date": ["date"]
    },
    {
      "name": "Bank B",
      "delimiter": [","],
      "description": ["booking_text"],
      "date": ["transaction_date"]
    }
  ],
  "qif_aliases": {
    "bank_a": "Assets:Current Assets:Bank A",
    "bank_b": "Assets:Current Assets:Bank B"
  },
  "skip_descriptions": ["Opening balance", "Turnover", "closing balance"],
  "mappings": [
    ["Expenses:Bank Service Charge", ["Norris and Sons", "Lee"]],
    ["Income:Salary", ["Smith PLC"]],
    ["Expenses:Medical", ["medical", "hospital"]],
    ["Expenses:Sport", ["sport"]]
  ]
}
```

## Help

```bash
$ csv2qif --help
Convert CSV file to QIF file.

Usage: csv2qif --format <FORMAT> --account <ACCOUNT> --config <CONFIG> <INPUT> <OUTPUT>

Arguments:
  <INPUT>   Path to input CSV file
  <OUTPUT>  Path to output QIF file

Options:
  -f, --format <FORMAT>    Format to be used from config file
  -a, --account <ACCOUNT>  Key in qif_aliases which is used as account name in QIF file
  -c, --config <CONFIG>    Path to config file
  -h, --help               Print help
  -V, --version            Print version
```

## Development

### Get coverage

#### Install libraries

```bash
cargo install cargo-llvm-cov --locked
```

#### Run coverage

```bash
make cov
```
