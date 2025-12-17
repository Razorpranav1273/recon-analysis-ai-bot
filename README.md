# Recon Analysis Slack Bot

A Slack bot for analyzing reconciliation data that integrates with the recon service APIs and Trino/Querybook. The bot performs three types of analysis:

1. **Scenario A**: Identifies records where `recon_at` is not updated in `txn_entity`
2. **Scenario B**: Identifies missing internal data for MIS records
3. **Scenario C**: Analyzes rule matching failures for unreconciled records

## Features

- Slack slash command `/recon-analyze` for easy access
- Integration with recon service APIs
- Trino/Querybook integration for data queries
- Three comprehensive analysis scenarios
- **AI-powered analysis** using Azure OpenAI for intelligent suggestions
- Intelligent ART remarks generation using LLM
- AI-enhanced Slack message explanations
- Rich Slack Block Kit message formatting
- Structured logging and error handling

## Architecture

```
recon-analysis-bot/
├── src/
│   ├── bot/              # Slack bot handlers
│   ├── analysis/          # Analysis engines (3 scenarios)
│   ├── services/          # API clients (recon, Trino, Slack)
│   └── utils/             # Configuration, logging, HTTP
├── config/                # TOML configuration files
└── tests/                 # Test files
```

## Setup

### Prerequisites

- Python 3.11+
- Access to recon service APIs
- Trino/Querybook access (for devserve.toml)
- Slack App credentials
- **AI Options** (choose one):
  - **Ollama** (recommended - free, open source, local) - OR
  - Azure OpenAI API credentials (cloud-based, paid)

### Installation

1. **Clone and setup**:
```bash
cd recon-analysis-bot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
export APP_ENV=dev  # or 'devserve' for prod Trino connection
export RECON_API_KEY="your-recon-api-key"
export SLACK_SIGNING_SECRET="your-slack-signing-secret"
export SLACK_BOT_TOKEN="your-slack-bot-token"
export TRINO_USERNAME="your-trino-username"  # For devserve

# AI Configuration (choose one):

# Option 1: Ollama (Recommended - Free, Open Source, Local)
# Install Ollama: https://ollama.ai
# Then run: ollama pull llama2
# No environment variables needed - just enable in config/dev.toml

# Option 2: Azure OpenAI (Cloud-based, Paid)
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_API_KEY="your-azure-openai-key"
export AZURE_OPENAI_DEPLOYMENT="your-deployment-name"
```

3. **Update configuration files**:
   - Edit `config/dev.toml` for development
   - Edit `config/devserve.toml` for production Trino connection

### Configuration

Configuration is managed through TOML files in the `config/` directory:

- **`default.toml`**: Base configuration
- **`dev.toml`**: Development overrides
- **`devserve.toml`**: Devserve config for prod Trino connection

Key configuration sections:

```toml
[recon]
base_url = "https://recon-service.example.com"
api_key = "${RECON_API_KEY}"

[trino]
host = "trino-prod.example.com"
port = 443
catalog = "hive"
schema = "default"
username = "${TRINO_USERNAME}"

[slack]
signing_secret = "${SLACK_SIGNING_SECRET}"
bot_token = "${SLACK_BOT_TOKEN}"

# AI Configuration - Choose Ollama (free) or Azure OpenAI (paid)

# Option 1: Ollama (Free, Open Source, Local)
[ollama]
enabled = true
base_url = "http://localhost:11434"
model = "llama2"

# Option 2: Azure OpenAI (Cloud-based, Paid)
[azure]
endpoint = "${AZURE_OPENAI_ENDPOINT}"
api_key = "${AZURE_OPENAI_API_KEY}"
deployment = "${AZURE_OPENAI_DEPLOYMENT}"
api_version = "2024-02-15-preview"
temperature = 0.2
max_tokens = 4000
```

## Running the Bot

### Development

```bash
export APP_ENV=dev
python -m src.bot.slack_bot
```

The bot will start on port 3000 (configurable via `PORT` environment variable).

### Production

```bash
export APP_ENV=devserve
gunicorn -w 4 -b 0.0.0.0:3000 src.bot.slack_bot:flask_app
```

## Usage

### Slack Command

Use the `/recon-analyze` slash command in Slack:

```
/recon-analyze workspace=WORKSPACE_NAME [report_url=URL]
```

**Parameters:**
- `workspace`: (Required) Name of the workspace to analyze
- `report_url`: (Optional) URL to ART report file (CSV/Excel)

**Example:**
```
/recon-analyze workspace=merchant_abc report_url=https://example.com/report.xlsx
```

### API Endpoints

- `GET /health` - Health check endpoint
- `POST /slack/events` - Slack events endpoint (used by Slack)

## Analysis Scenarios

### Scenario A: recon_at Not Updated

Identifies records where:
- `recon_status = 'Reconciled'` in recon_result
- `recon_at` timestamp exists in recon_result
- `recon_at` is missing in txn_entity table

**Output**: List of records needing txn_entity update

### Scenario B: Missing Internal Data

Identifies:
- MIS records with no matching internal record
- Checks if internal file ingestion exists
- Suggests re-ingestion if file exists but records missing

**Output**: List of missing internal records with suggestions

### Scenario C: Rule Matching Failures

For unreconciled records with both internal and MIS data:
- Fetches applicable rules from recon system
- Evaluates rules against record data
- Identifies which rule failed and why
- **Uses AI (Azure OpenAI) to generate intelligent art_remarks** based on:
  - Rule expression and failure context
  - Mismatch details (amount, RRN, etc.)
  - Internal and MIS data comparison
- Falls back to rule-based suggestions if AI is unavailable

**Output**: Detailed rule failure analysis with AI-powered suggestions

## Integration Points

### Recon Service APIs

- `/api/v1/workspaces` - Get workspace by name
- `/api/v1/records` - Fetch unreconciled records
- `/api/v1/recon_result` - Get reconciliation results
- `/api/v1/rules` - Get rule configurations
- `/api/v1/file_types` - Get file type metadata

### Trino/Querybook

- Query `txn_entity` table for `recon_at` timestamps
- Custom Querybook queries (to be provided)
- File ingestion logs (if needed)

## Development

### Project Structure

- `src/bot/` - Slack bot handlers and commands
- `src/analysis/` - Analysis engines for three scenarios
- `src/services/` - API clients (recon, Trino, Slack formatting)
- `src/utils/` - Configuration, logging, HTTP utilities

### Adding New Analysis Scenarios

1. Create new analyzer in `src/analysis/`
2. Add analysis call in `src/bot/commands.py`
3. Add formatting in `src/services/slack_service.py`

### Testing

```bash
pytest tests/
```

## Troubleshooting

### Common Issues

1. **Slack credentials not working**:
   - Verify `SLACK_SIGNING_SECRET` and `SLACK_BOT_TOKEN` are set
   - Check Slack App configuration

2. **Recon API errors**:
   - Verify `RECON_API_KEY` is set
   - Check `recon.base_url` in config

3. **Trino connection errors**:
   - Verify Trino credentials in `devserve.toml`
   - Check network connectivity to Trino host

## License

Internal use only.

## Support

For issues or questions, contact the development team.

