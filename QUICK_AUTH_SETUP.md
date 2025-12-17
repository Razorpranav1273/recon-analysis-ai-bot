# Quick Auth Setup

## Your Credentials (from teammate)

**Basic Auth Token:** `Basic cmVjb25fYXBpX3VzZXI6c3RhZ2UuYXBpQGFydA==`

**Decoded:**
- Username: `recon_api_user`
- Password: `stage.api@art`

---

## Quick Setup (Choose One Method)

### Method 1: Use Basic Auth Token Directly (Easiest) ✅

```bash
export RECON_BASIC_AUTH_TOKEN="Basic cmVjb25fYXBpX3VzZXI6c3RhZ2UuYXBpQGFydA=="
```

**OR** update `config/dev.toml`:
```toml
[recon]
basic_auth_token = "Basic cmVjb25fYXBpX3VzZXI6c3RhZ2UuYXBpQGFydA=="
```

### Method 2: Use Username + Password

```bash
export RECON_API_USERNAME="recon_api_user"
export RECON_API_PASSWORD="stage.api@art"
```

**OR** update `config/dev.toml`:
```toml
[recon]
api_username = "recon_api_user"
api_password = "stage.api@art"
```

---

## Complete Setup Command

```bash
cd /Users/pranav.desai/Documents/Hackathon/recon-analysis-ai-bot

# Set all tokens
export SLACK_BOT_TOKEN="your-slack-bot-token"
export SLACK_APP_TOKEN="your-slack-app-token"
export RECON_BASIC_AUTH_TOKEN="Basic your-base64-encoded-credentials"

# Start bot
python3 run_socket.py
```

---

## Test

In Slack:
```
@Recon Analysis Bot analyze workspace NETBANKING_SBI
```

You should see the analysis results instead of the 403 error!

---

## Verify It's Working

When you start the bot, check the terminal logs. You should see:
```
Recon client initialized with Basic Auth token
base_url=http://localhost:5000
```

If you see this, authentication is working! ✅

