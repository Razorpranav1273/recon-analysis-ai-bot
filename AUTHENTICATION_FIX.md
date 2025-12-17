# Fix: HTTP 403 Forbidden Error

## Problem
You're getting `Error: HTTP 403: Forbidden` when trying to analyze a workspace.

## Root Cause
The recon service uses **Basic Authentication** (username:password), but the bot was using **Bearer token** authentication.

## Solution

### Step 1: Get Your Recon API Credentials

You need:
- **Username**: `recon_api_user` (this is the standard username)
- **Password**: `RECON_API_SECRET_KEY` (this is from your environment/config)

**How to find your password:**
1. Check your recon service configuration
2. Look for environment variable: `RECON_API_SECRET_KEY`
3. Or check your config files for `RECON_API_SECRET_KEY`

### Step 2: Set Environment Variables

Export these in your terminal:

```bash
export RECON_API_USERNAME="recon_api_user"
export RECON_API_PASSWORD="your-actual-secret-key-here"
```

**OR** update your `config/dev.toml`:

```toml
[recon]
base_url = "http://localhost:5000"
api_username = "recon_api_user"
api_password = "your-actual-secret-key-here"
```

### Step 3: Restart Your Bot

```bash
cd /Users/pranav.desai/Documents/Hackathon/recon-analysis-ai-bot
export SLACK_BOT_TOKEN="your-slack-bot-token"
export SLACK_APP_TOKEN="your-slack-app-token"
export RECON_API_USERNAME="your-username"
export RECON_API_PASSWORD="your-password"
python3 run_socket.py
```

### Step 4: Test Again

In Slack:
```
@Recon Analysis Bot analyze workspace NETBANKING_SBI
```

---

## How to Find Your RECON_API_SECRET_KEY

### Option 1: Check Environment Variables
```bash
echo $RECON_API_SECRET_KEY
```

### Option 2: Check Recon Service Config
Look in your recon service configuration files for `RECON_API_SECRET_KEY`.

### Option 3: Ask Your Team
Ask someone who has access to the recon service configuration.

### Option 4: Check Common Config Files
- `.env` files
- `config/devserve.toml` or similar
- Environment variable exports

---

## What Changed

### Before (Wrong):
```python
Authorization: Bearer <api_key>
```

### After (Correct):
```python
Authorization: Basic <base64(username:password)>
```

The bot now:
1. Tries Basic Auth first (username:password)
2. Falls back to Bearer token if username/password not provided
3. Logs which authentication method is being used

---

## Verification

When you start the bot, you should see in the terminal:
```
Recon client initialized with Basic Auth
base_url=http://localhost:5000
username=recon_api_user
```

If you see this, authentication is configured correctly!

---

## Still Getting 403?

1. **Verify credentials are correct:**
   - Username should be: `recon_api_user`
   - Password should match your `RECON_API_SECRET_KEY`

2. **Check base_url:**
   - Make sure `base_url` points to the correct recon service
   - For local: `http://localhost:5000`
   - For devserve: Check your actual URL

3. **Check if service is running:**
   ```bash
   curl -u recon_api_user:YOUR_PASSWORD http://localhost:5000/api/v1/workspaces
   ```

4. **Check terminal logs:**
   - Look for authentication errors
   - Check what URL is being called
   - Verify headers are being set

---

## Quick Test

Test the API directly:
```bash
curl -u recon_api_user:YOUR_PASSWORD \
  http://localhost:5000/api/v1/workspaces
```

If this works, the bot should work too!

