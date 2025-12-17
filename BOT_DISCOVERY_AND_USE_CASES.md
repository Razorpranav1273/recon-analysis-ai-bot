# Bot Discovery & Use Cases

## How People Will Discover the Bot

### 1. **Channel Invitation**
- Bot is invited to `#test_recon_alerts` (or other recon channels)
- People see the bot in the channel member list
- Bot appears as "Recon Analysis Bot" in Slack

### 2. **Word of Mouth**
- Team members share: "Hey, use @Recon Analysis Bot to check workspaces"
- Documentation mentions the bot
- Onboarding guides include bot usage

### 3. **Slash Commands Discovery**
- Users type `/` in Slack and see:
  - `/recon-analyze` - Analyze reconciliation data
  - `/recon-list-workspaces` - List all workspaces
- Slack autocomplete shows these commands

### 4. **Bot Mentions**
- Users can mention: `@Recon Analysis Bot help`
- Bot responds with available commands

---

## Current Bot Capabilities

### ✅ What the Bot Can Do NOW:

1. **List Workspaces**
   ```
   @Recon Analysis Bot list workspaces
   /recon-list-workspaces
   ```
   → Shows all available recon workspaces

2. **Analyze Workspace**
   ```
   @Recon Analysis Bot analyze workspace NETBANKING_SBI
   /recon-analyze workspace=NETBANKING_SBI
   ```
   → Runs 3 analysis scenarios:
   - Scenario A: Missing `recon_at` updates
   - Scenario B: Missing internal data
   - Scenario C: Rule matching failures

3. **Get Help**
   ```
   @Recon Analysis Bot help
   ```
   → Shows available commands

---

## What Happens with "Dual Write Problem"?

### ❌ Current Behavior:

If someone types:
```
@Recon Analysis Bot dual write problem
```

**The bot will respond:**
```
I can help you with reconciliation analysis! Here's what I can do:
• List workspaces: @Recon Analysis Bot list workspaces
• Analyze workspace: @Recon Analysis Bot analyze workspace NAME
• Get help: @Recon Analysis Bot help
```

**Why?** The bot currently uses **keyword matching** and doesn't understand "dual write problem" as a specific intent.

### ✅ What We CAN Add:

We can enhance the bot to understand "dual write problems" using **Ollama AI**:

1. **AI-Powered Intent Detection**
   - User: "dual write problem in NETBANKING_SBI"
   - Ollama extracts: Intent = "analyze_dual_write", Workspace = "NETBANKING_SBI"
   - Bot: Runs dual write analysis

2. **AI-Powered Problem Understanding**
   - User: "why is dual write failing?"
   - Ollama understands: User wants explanation of dual write failures
   - Bot: Analyzes dual write issues and explains using AI

---

## Ollama Use Cases (Current & Potential)

### ✅ Current Ollama Usage:

#### 1. **ART Remarks Generation** (Rule Analyzer)
**Location:** `src/analysis/rule_analyzer.py`

**What it does:**
- When a rule fails to match records, Ollama generates intelligent `art_remarks`
- Explains WHY the rule failed in human-readable format

**Example:**
```
Rule Failed: Amount mismatch
Internal Data: ₹1000.00
MIS Data: ₹1000.50

Ollama generates:
"Amount mismatch detected: Expected ₹1000.00 but found ₹1000.50. 
Possible causes: Rounding differences, fee deductions, or data sync issues. 
Recommendation: Check fee calculation logic and verify data source."
```

**Without Ollama:**
```
"Amount mismatch: Internal=1000.00, MIS=1000.50"
```

#### 2. **Summary Explanations** (Slack Service)
**Location:** `src/services/slack_service.py`

**What it does:**
- After analysis completes, Ollama generates a summary explanation
- Explains findings in plain language with context

**Example:**
```
Summary:
- Scenario A: 5 records
- Scenario B: 3 records
- Scenario C: 2 records

Ollama generates:
"Found 5 records where recon_at was not updated despite reconciliation. 
This suggests a data synchronization issue between the recon service and txn_entity table. 
3 records are missing internal data, which may indicate ingestion pipeline problems. 
2 rule failures suggest potential data quality issues that need investigation."
```

**Without Ollama:**
```
"Summary: 5 records, 3 records, 2 records"
```

---

### 🚀 Potential Ollama Enhancements:

#### 3. **Natural Language Understanding** (Not Yet Implemented)
**What it could do:**
- Understand user queries in natural language
- Extract intent and parameters from any format

**Example:**
```
User: "check why NETBANKING_SBI workspace is having dual write issues"
Ollama extracts:
- Intent: analyze_dual_write
- Workspace: NETBANKING_SBI
- Problem: dual write issues

Bot: Runs dual write analysis for NETBANKING_SBI
```

#### 4. **Dual Write Problem Analysis** (Not Yet Implemented)
**What it could do:**
- Analyze dual write failures
- Explain root causes using AI
- Suggest solutions

**Example:**
```
User: "analyze dual write problem for NETBANKING_SBI"
Bot: 
1. Fetches dual write data
2. Analyzes failures
3. Ollama generates:
   "Dual write failures detected: 10 records failed to sync to PRS.
   Common causes: Network timeouts (3), Invalid payload format (5), 
   Missing required fields (2). Recommendation: Check network connectivity 
   and verify payload structure matches PRS requirements."
```

#### 5. **Intelligent Error Explanations** (Not Yet Implemented)
**What it could do:**
- Convert technical errors to user-friendly explanations
- Suggest fixes

**Example:**
```
Error: "Connection refused on port 5000"
Ollama explains:
"The recon service is not responding. Possible causes:
1. Service is down - check if it's running
2. Port 5000 is blocked - check firewall settings
3. Service crashed - check logs

Suggested actions:
1. Restart the recon service
2. Check service health endpoint
3. Contact platform-recon team"
```

---

## How to Add Dual Write Problem Support

### Step 1: Add Dual Write Analysis
Create a new analyzer that:
- Fetches dual write data from recon service
- Identifies failed dual write records
- Analyzes failure patterns

### Step 2: Add AI-Powered Intent Detection
Use Ollama to understand:
- "dual write problem"
- "dual write failing"
- "dual write issues"
- "check dual write for workspace X"

### Step 3: Integrate with Bot
Add handler in `commands.py`:
```python
if "dual write" in cleaned_text:
    workspace = extract_workspace(cleaned_text)
    return analyze_dual_write(workspace)
```

---

## Summary

### Current State:
- ✅ Bot is discoverable via mentions and slash commands
- ✅ Ollama used for ART remarks and summaries
- ❌ Bot doesn't understand "dual write problem" yet

### With Enhancements:
- ✅ Bot understands natural language queries
- ✅ Bot can analyze dual write problems
- ✅ Ollama provides intelligent explanations

**Would you like me to implement dual write problem analysis with Ollama?**

