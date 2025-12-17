# Quick Fix: Bot Not Responding to Mentions

## The Problem
Bot responds to `/recon-analyze` but NOT to `@Recon Analysis Bot` mentions.

## The Solution (3 Steps)

### ✅ Step 1: Enable Event Subscriptions

1. **Go to Event Subscriptions:**
   - Open: https://api.slack.com/apps/A0A3XLJ12Q3/event-subscriptions

2. **Enable Events:**
   - Toggle **"Enable Events"** to **ON** (top of page)

3. **Add Bot Event:**
   - Scroll to **"Subscribe to bot events"** section
   - Click **"Add Bot User Event"**
   - Type: `app_mentions`
   - Click **"Save Changes"**

### ✅ Step 2: Reinstall App

1. **Go to Install App:**
   - Open: https://api.slack.com/apps/A0A3XLJ12Q3/install-app

2. **Reinstall:**
   - Click **"Reinstall to Razorpay"** button
   - Click **"Allow"** to confirm

### ✅ Step 3: Restart Bot

**Stop the bot** (if running):
- Press `Ctrl+C` in the terminal where bot is running

**Start the bot:**
```bash
cd /Users/pranav.desai/Documents/Hackathon/recon-analysis-ai-bot
export SLACK_BOT_TOKEN="your-slack-bot-token"
export SLACK_APP_TOKEN="your-slack-app-token"
python3 run_socket.py
```

### ✅ Step 4: Test

In `#test_recon_alerts`, type:
```
@Recon Analysis Bot help
```

**Expected:**
- Bot responds with help message
- Terminal shows: `Received app mention`

**If still not working:**
- Check terminal for errors
- Verify `app_mentions` appears in "Subscribe to bot events" list
- Make sure bot is running (check terminal)

---

## Visual Guide

**Event Subscriptions Page Should Show:**
```
✅ Enable Events: ON

Subscribe to bot events:
  • app_mentions
```

**After Reinstall, You Should See:**
- Green checkmark ✅
- "Successfully installed" message

