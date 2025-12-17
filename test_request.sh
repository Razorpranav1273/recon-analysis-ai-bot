#!/bin/bash
# Test script to send a request to the running Flask app

curl -X POST http://localhost:3000/test/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_name": "NETBANKING_AUSF",
    "file_type": "bank_payment_report",
    "unique_column_value": "RrQHFDvwIQIKiH"
  }' | python3 -m json.tool

