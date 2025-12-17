# Debugging Slack Integration

## Issue: Messages not reaching local bot

### Common Issues:

1. **Invalid Tokens**
   - Bot tokens should be ~50+ characters (xoxb-...)
   - App tokens should be ~50+ characters (xapp-...)
   - Check: `echo $SLACK_BOT_TOKEN | wc -c` (should be > 50)
   - Check: `echo $SLACK_APP_TOKEN | wc -c` (should be > 50)

2. **Socket Mode Not Enabled**
   - Go to https://api.slack.com/apps
   - Select your app
   - Go to "Socket Mode" in left sidebar
   - Enable Socket Mode
   - Generate an App-Level Token with `connections:write` scope

3. **Event Subscriptions Not Configured**
   - Go to "Event Subscriptions" in Slack app settings
   - Enable Events
   - Subscribe to bot events:
     - `app_mentions:read`
     - `message.channels` (if needed)
   - Subscribe to workspace events (if needed)

4. **Bot Not Added to Channel**
   - Invite bot to channel: `/invite @Recon Analysis Bot`
   - Or mention it: `@Recon Analysis Bot help`

5. **Multiple Servers Running**
   - Stop all Flask servers: `pkill -f "run.py"`
   - Stop socket mode: `pkill -f "run_socket.py"`
   - Start only socket mode: `python run_socket.py`

### Testing Steps:

1. **Check tokens are set:**
   ```bash
   cd /Users/nithin.borusu/Documents/repos/recon-analysis-ai-bot
   source .venv/bin/activate
   export APP_ENV=dev
   python -c "
   from src.utils.config_reader import get_config_value
   bot_token = get_config_value('slack.bot_token', '')
   app_token = get_config_value('slack.app_token', '')
   print(f'Bot Token: {len(bot_token)} chars, starts with: {bot_token[:10]}...')
   print(f'App Token: {len(app_token)} chars, starts with: {app_token[:10]}...')
   "
   ```

2. **Start socket mode bot:**
   ```bash
   cd /Users/nithin.borusu/Documents/repos/recon-analysis-ai-bot
   source .venv/bin/activate
   export APP_ENV=dev
   python run_socket.py
   ```

3. **Watch for connection:**
   - Should see: "Bot is connecting to Slack via Socket Mode..."
   - Should see: "Waiting for Slack events..."
   - If you see errors, check tokens

4. **Test in Slack:**
   - Go to a channel where bot is added
   - Type: `@Recon Analysis Bot workspace_name=NETBANKING_AUSF file_type=bank_payment_report unique_column_value=RrQHFDvwIQIKiH`
   - Check terminal for: "🔔 APP MENTION EVENT RECEIVED!"

### If Still Not Working:

1. **Check Slack App Logs:**
   - Go to https://api.slack.com/apps
   - Select your app
   - Go to "Logs" in left sidebar
   - Check for errors

2. **Verify Bot User ID:**
   - In Slack, right-click on bot name → "View profile"
   - Note the User ID (starts with U)
   - Make sure it matches in your app settings

3. **Check OAuth Scopes:**
   - Go to "OAuth & Permissions"
   - Bot Token Scopes should include:
     - `app_mentions:read`
     - `chat:write`
     - `commands`
     - `channels:read` (if needed)

