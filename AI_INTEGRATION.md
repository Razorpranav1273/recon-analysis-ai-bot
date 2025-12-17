# AI Integration (Ollama & Azure OpenAI)

## Overview

The recon-analysis-bot now includes AI integration with **two options**:
1. **Ollama** (Recommended) - Free, open-source, runs locally
2. **Azure OpenAI** - Cloud-based, paid service

Both follow the same pattern as `poc_risk_agent` and provide AI-powered analysis and intelligent suggestions.

## What's Added

### 1. LLM Utilities Module
- **File**: `src/utils/llm_utils.py`
- **Features**:
  - **Ollama** client creation (ChatOllama via LangChain)
  - **Azure OpenAI** client creation via LangChain
  - Retry logic with exponential backoff for rate limits
  - Token estimation using tiktoken
  - Rate limit error handling
  - Configurable retry parameters
  - Automatic fallback: Ollama → Azure OpenAI → Rule-based

### 2. AI-Powered ART Remarks Generation
- **File**: `src/analysis/rule_analyzer.py`
- **Enhancement**: 
  - Uses Azure OpenAI to generate intelligent `art_remarks` suggestions
  - Analyzes rule failures, mismatch details, and data context
  - Falls back to rule-based suggestions if AI is unavailable
  - Provides contextual, actionable remarks

### 3. AI-Enhanced Slack Messages
- **File**: `src/services/slack_service.py`
- **Enhancement**:
  - Generates AI-powered summary explanations
  - Provides business-friendly analysis insights
  - Enhances user understanding of findings

### 4. Prompts Module
- **File**: `src/analysis/prompts.py`
- **Contains**:
  - ART remarks generation prompt template
  - Analysis explanation prompt template
  - Customizable prompts for different use cases

### 5. Configuration Updates
- **Files**: `config/default.toml`, `config/dev.toml`, `config/devserve.toml`
- **Added**:
  - `[ollama]` section with enabled flag, base_url, model selection
  - `[azure]` section with endpoint, API key, deployment settings
  - `[llm]` section with retry configuration
  - Environment variable support

### 6. Dependencies
- **Files**: `requirements.txt`, `pyproject.toml`
- **Added**:
  - `langchain-openai>=0.1.0`
  - `openai>=1.0.0`
  - `tiktoken>=0.5.0`

## Configuration

### Option 1: Ollama (Recommended - Free, Local)

**Setup**:
1. Install Ollama: https://ollama.ai
2. Start service: `ollama serve`
3. Pull model: `ollama pull llama2`

**Config**:
```toml
[ollama]
enabled = true
base_url = "http://localhost:11434"
model = "llama2"  # or llama3, mistral, etc.
```

### Option 2: Azure OpenAI (Cloud, Paid)

**Environment Variables**:
```bash
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_API_KEY="your-azure-openai-key"
export AZURE_OPENAI_DEPLOYMENT="your-deployment-name"
```

**Config**:
```toml
[azure]
endpoint = "${AZURE_OPENAI_ENDPOINT}"
api_key = "${AZURE_OPENAI_API_KEY}"
api_version = "2024-02-15-preview"
deployment = "${AZURE_OPENAI_DEPLOYMENT}"
temperature = 0.2
max_tokens = 4000

[llm]
max_attempts = 3
initial_backoff_s = 5
backoff_factor = 2.0
max_backoff_s = 60
jitter_s = 1.0
respect_retry_after = true
```

## How It Works

### Priority Order

The bot tries AI in this order:
1. **Ollama** (if `ollama.enabled = true`) - Local, free
2. **Azure OpenAI** (if configured) - Cloud, paid
3. **Rule-based** - Always works as fallback

### 1. ART Remarks Generation

When a rule fails:
1. Rule analyzer detects the failure and mismatch details
2. If LLM is available (Ollama or Azure OpenAI), calls AI with:
   - Rule ID and expression
   - Mismatch details (amount, RRN, etc.)
   - Internal and MIS data context
3. AI generates intelligent, contextual ART remark
4. Falls back to rule-based remark if AI fails

### 2. Summary Explanations

In Slack messages:
1. After analysis completes, generates summary statistics
2. If LLM is available, creates AI-powered explanation
3. Explains findings in business-friendly terms
4. Enhances user understanding

## Benefits

1. **Intelligent Suggestions**: AI understands context and generates relevant remarks
2. **Better User Experience**: Clear, actionable explanations
3. **Free Option**: Ollama provides free, local AI (no API costs)
4. **Privacy**: Ollama keeps data local (no cloud transmission)
5. **Graceful Degradation**: Falls back to rule-based if AI unavailable
6. **Production Ready**: Includes retry logic, error handling, rate limit management
7. **Flexible**: Choose between local (Ollama) or cloud (Azure OpenAI)

## Usage

The AI integration is automatic when configured. No code changes needed!

**To use Ollama**:
1. Install and start Ollama
2. Set `ollama.enabled = true` in config
3. Bot automatically uses Ollama

**To use Azure OpenAI**:
1. Set environment variables or config values
2. Bot automatically uses Azure OpenAI (if Ollama not enabled)

**If neither is configured**: Bot works normally with rule-based suggestions.

## Testing

To test AI features:
1. Configure Azure OpenAI credentials
2. Run analysis with rule failures
3. Check Slack messages for AI-generated remarks and explanations
4. Verify fallback behavior by temporarily disabling credentials

## Future Enhancements

Potential improvements:
- Fine-tuned models for reconciliation domain
- Caching of similar suggestions
- Multi-language support
- Custom prompt templates per workspace
- Learning from user feedback

