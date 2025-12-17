# Ollama Setup Guide

## What is Ollama?

Ollama is a free, open-source tool that lets you run large language models locally on your machine. No API keys, no costs, complete privacy.

## Installation

### macOS
```bash
brew install ollama
```

### Linux
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### Windows
Download from: https://ollama.ai/download

## Quick Start

1. **Start Ollama service**:
   ```bash
   ollama serve
   ```
   Keep this running in a terminal.

2. **Pull a model** (in another terminal):
   ```bash
   # Recommended models for reconciliation analysis:
   ollama pull llama2        # Good balance (7B params)
   ollama pull llama3        # Better quality (8B params)
   ollama pull mistral       # Fast and efficient
   ollama pull codellama     # Good for technical tasks
   ```

3. **Verify installation**:
   ```bash
   ollama list              # See installed models
   ollama run llama2 "Hello"  # Test a model
   ```

## Configuration

### Enable Ollama in Bot

Edit `config/dev.toml`:
```toml
[ollama]
enabled = true
base_url = "http://localhost:11434"
model = "llama2"  # Change to your preferred model
```

### Available Models

Run `ollama list` to see installed models. Popular options:

- **llama2** - Good balance, 7B parameters
- **llama3** - Better quality, 8B parameters  
- **mistral** - Fast and efficient
- **codellama** - Good for technical/code tasks
- **phi** - Small and fast (2.7B params)

### Model Selection Tips

- **For development/testing**: Use `llama2` or `mistral` (faster)
- **For production**: Use `llama3` (better quality)
- **For low-resource systems**: Use `phi` (smallest)

## How It Works

1. Bot checks if Ollama is enabled in config
2. If enabled, connects to local Ollama service
3. Uses selected model for AI-powered suggestions
4. Falls back to Azure OpenAI if Ollama unavailable
5. Falls back to rule-based if no AI available

## Troubleshooting

### Ollama not starting
```bash
# Check if port 11434 is available
lsof -i :11434

# Restart Ollama
pkill ollama
ollama serve
```

### Model not found
```bash
# List available models
ollama list

# Pull the model you need
ollama pull llama2
```

### Connection refused
- Make sure `ollama serve` is running
- Check `base_url` in config matches Ollama server
- Default: `http://localhost:11434`

### Slow responses
- Use smaller models (phi, mistral) for faster responses
- Ensure you have enough RAM (models need 4-8GB+)
- Close other applications to free up memory

## Benefits

✅ **Free** - No API costs  
✅ **Private** - Data stays on your machine  
✅ **Offline** - Works without internet  
✅ **Open Source** - No vendor lock-in  
✅ **Flexible** - Multiple model options  

## Performance

- **Response time**: 2-10 seconds (depends on model and hardware)
- **Memory usage**: 4-16GB RAM (depends on model)
- **CPU**: Works on CPU, faster with GPU

## Next Steps

1. Install Ollama
2. Pull a model (`ollama pull llama2`)
3. Enable in `config/dev.toml` (`ollama.enabled = true`)
4. Run the bot - it will use Ollama automatically!

