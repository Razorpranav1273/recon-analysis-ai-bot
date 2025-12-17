#!/bin/bash

# Script to push recon-analysis-ai-bot to GitHub

cd "$(dirname "$0")"

echo "🚀 Initializing git repository..."
git init

echo "📦 Adding all files..."
git add .

echo "💾 Creating initial commit..."
git commit -m "Initial commit: Recon Analysis AI Bot with Ollama and Azure OpenAI integration"

echo "🌿 Setting main branch..."
git branch -M main

echo "🔗 Adding remote repository..."
git remote add origin https://github.com/Razorpranav1273/recon-analysis-ai-bot.git 2>/dev/null || git remote set-url origin https://github.com/Razorpranav1273/recon-analysis-ai-bot.git

echo "⬆️  Pushing to GitHub..."
echo "⚠️  Note: You may be prompted for GitHub credentials"
git push -u origin main

echo "✅ Done! Check your repository at: https://github.com/Razorpranav1273/recon-analysis-ai-bot"

