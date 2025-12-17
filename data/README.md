# Data Directory

This directory contains test data files for the recon analysis bot.

## Structure

```
data/
├── raw/              # Raw data files (CSV, JSON)
│   ├── data.json                    # Workspace and file type data
│   ├── journal_data.csv              # Journal records from Hudi tables
│   ├── payments.csv                  # Payments table data
│   ├── recon_rules.csv              # Rules and rule_recon_state_map data
│   └── transactions_db.csv          # Transactions table data
└── README.md         # This file
```

## Files Description

- **data.json**: Contains workspace metadata and file type configurations
- **journal_data.csv**: Sample journal records from Hudi tables with recon status
- **payments.csv**: Payments table data for checking payment existence and data lag
- **recon_rules.csv**: Rules, rule_recon_state_map, and recon_state data
- **transactions_db.csv**: Transactions table data for checking reconciled_at status

## Usage

These files are loaded into the local SQLite database using:
```bash
python -m src.data.load_test_data
```

The data is stored in `local_db.sqlite` in the project root.
