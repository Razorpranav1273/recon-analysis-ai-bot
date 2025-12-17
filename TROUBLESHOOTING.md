# Troubleshooting Guide

## Bot Not Responding to Mentions

If the bot doesn't respond when you mention it (`@Recon Analysis Bot`), check the following:

### Step 1: Verify Bot is Running

Check if the bot process is running:
```bash
ps aux | grep "run_socket.py" | grep -v grep
```

If not running, start it:
```bash
cd /Users/pranav.desai/Documents/Hackathon/recon-analysis-ai-bot
export SLACK_BOT_TOKEN="your-slack-bot-token"
export SLACK_APP_TOKEN="your-slack-app-token"
python3 run_socket.py
```

### Step 2: Enable Event Subscriptions in Slack

**CRITICAL:** Even in Socket Mode, you need to subscribe to events in Slack App settings.

1. Go to: https://api.slack.com/apps/A0A3XLJ12Q3/event-subscriptions
2. Make sure **"Enable Events"** is turned **ON**
3. Under **"Subscribe to bot events"**, add:
   - `app_mentions` (for @bot mentions)
   - `message.channels` (if you want to listen to all channel messages)
4. Click **"Save Changes"**
5. **Reinstall the app** if prompted:
   - Go to "Install App" in the left sidebar
   - Click "Reinstall to Razorpay"

### Step 3: Check Terminal Logs

When you mention the bot, you should see logs in the terminal:
```
Received app mention
original_text=...
cleaned_text=...
```

If you see errors, share them for debugging.

### Step 4: Verify Bot Permissions

Go to: https://api.slack.com/apps/A0A3XLJ12Q3/oauth-permissions

Make sure these **Bot Token Scopes** are added:
- `app_mentions:read` (to receive mentions)
- `chat:write` (to send messages)
- `commands` (for slash commands)

### Step 5: Test Again

After making changes:
1. Restart the bot
2. In Slack, type: `@Recon Analysis Bot help`
3. Check terminal for logs
4. Check Slack for bot response

## Common Issues

### Issue: "Bot doesn't respond to mentions"
**Solution:** Enable `app_mentions` event subscription (Step 2 above)

### Issue: "Bot responds but with errors"
**Solution:** Check terminal logs and share error messages

### Issue: "Bot works for slash commands but not mentions"
**Solution:** This confirms the event subscription is missing - follow Step 2

