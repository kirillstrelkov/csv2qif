# CSV2QIF

Application which converts CSV format to QIF and categarize transactions based on config file.

Example usage with [config from tests](tests/public/config.json):

```bash
csv2qif.py /tmp/my_bank.csv /tmp/out.qif -c tests/public/config.json -f 'Bank A' -a bank_a
```

## Config file

Config file contains information about how to parse transactions from CSV file and how to format transaction in QIF file. See [test config](tests/public/config.json) for example.

Here is overview of keys in config file:

| key               | comment                                                                                 |
| ----------------- | --------------------------------------------------------------------------------------- |
| formats           | config for CSV file from one bank                                                       |
| gnucash_aliases   | QIF account name, shortcut which can be used with `-a` flag                             |
| skip_descriptions | Transactions which contain these text or match regexp will be skipped                   |
| mappings          | QIF account name and list of texts/regexps that will match transactions to this account |

Config example for one bank:

```json
{
  "formats": [
    {
      "name": "Bank A",
      "encoding": "utf8",
      "delimiter": ";",
      "description": ["details", "beneficiary_payer"],
      "date": "date"
    }
  ],
  "gnucash_aliases": {
    "bank_a": "Assets:Current Assets:Bank A"
  },
  "skip_descriptions": ["Opening balance", "closing balance"],
  "mappings": {
    "Expenses:Bank Service Charge": ["Bank A"],
    "Income:Salary": ["Smith PLC"],
    "Expenses:Medical": ["medical", "hospital"],
    "Expenses:Sport": ["sport"]
  }
}
```
