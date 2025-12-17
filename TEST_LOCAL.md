# Testing the Slack Bot Locally

## Step 1: Start the Flask Server

```bash
cd /Users/nithin.borusu/Documents/repos/recon-analysis-ai-bot
source .venv/bin/activate
export APP_ENV=dev
python run.py
```

The server will start on `http://localhost:3000`

## Step 2: Send a Test Request

In another terminal, send a POST request to the test endpoint:

```bash
curl -X POST http://localhost:3000/test/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_name": "NETBANKING_AIUSF",
    "file_type": "bank_payment_report",
    "unique_column_value": "RrQHFDvwIQIKiH"
  }'
```

Or use the test script:

```bash
./test_request.sh
```

## Request Parameters

- `workspace_name` (required): The workspace name (e.g., "NETBANKING_AIUSF")
- `file_type` (required): The file type name (e.g., "bank_payment_report")
- `unique_column_value` (required): The unique column value to analyze (e.g., payment_id)
- `date_start` (optional): Start date for transaction range
- `date_end` (optional): End date for transaction range

## Example with Date Range

```bash
curl -X POST http://localhost:3000/test/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_name": "NETBANKING_AIUSF",
    "file_type": "bank_payment_report",
    "unique_column_value": "RrQHFDvwIQIKiH",
    "date_start": "2025-12-14",
    "date_end": "2025-12-14"
  }'
```

