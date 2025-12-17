Quick local setup
Step 1: Install dependencies
cd recon-analysis-ai-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
Step 2: Set environment variables
export APP_ENV=dev
export SLACK_SIGNING_SECRET="your-secret"
export SLACK_BOT_TOKEN="xoxb-your-token"
export RECON_API_KEY="your-key"  # Optional
Step 3: Set up AI (choose one)
Option A: Ollama (free, local)
# Install Ollama
brew install ollama  # macO
# OR: curl -fsSL https://ollama.ai/install.sh | sh  # Linux
# Start Ollama
ollama serve
# Pull model (in new terminal)
ollama pull llama2
Then edit config/dev.toml:
[ollama]
enabled = true
Option B: Azure OpenAI
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_DEPLOYMENT="your-deployment"
Step 4: Run the bot
python run.py
Step 5: Expose to Slack (choose one)
Option A: ngrok (easiest)
ngrok http 3000
# Copy the URL and set in Slack app: https://xxxx.ngrok.io/slack/events
Option B: Local IP
Find your IP: ipconfig getifaddr en0 (macOS) or hostname -I (Linux)
Set Slack Request URL to: http://YOUR_IP:3000/slack/events
Step 6: Test
In Slack, type: /recon-analyze workspace=YOUR_WORKSPACE
Minimal setup (testing only)
# 1. Install
pip install -r requirements.txt
# 2. Set dummy env vars
export APP_ENV=dev
export SLACK_SIGNING_SECRET="dummy"
export SLACK_BOT_TOKEN="dummy"
# 3. Run
python run.py
Checklist
[ ] Dependencies installed (pip install -r requirements.txt)
[ ] Environment variables set (SLACK_SIGNING_SECRET, SLACK_BOT_TOKEN)
[ ] AI configured (Ollama running OR Azure OpenAI env vars)
[ ] Bot running (python run.py)
[ ] Slack app Request URL configured (ngrok or local IP)
[ ] Tested with /recon-analyze command
Troubleshooting
Port 3000 in use? → export PORT=3001
Ollama not working? → ollama serve (keep running)
Slack not connecting? → Check Request URL in Slack app settings

