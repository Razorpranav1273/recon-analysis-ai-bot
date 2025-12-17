# Recon Analysis Slack Bot - AI-Powered Roadmap

## Overview

This roadmap outlines the development of an AI-powered Slack bot for automated reconciliation analysis. The bot uses Ollama LLM to analyze three main scenarios where manual PSE intervention is typically required.

## Key AI Enhancements

### Advanced Prompt Engineering
- **Chain-of-Thought Reasoning**: Multi-step analysis with explicit reasoning
- **Few-Shot Learning**: Examples in prompts for better accuracy
- **Structured Outputs**: JSON schema for consistent parsing
- **Context Enrichment**: Full workspace/rules/history context

### Batch Processing & Pattern Recognition
- Analyze multiple records together to identify patterns
- Group similar failures for bulk recommendations
- Identify root causes across record clusters

### Enhanced Rule Analysis
- Full integration with `rule_recon_state_map` and `recon_state` tables
- Rule sequence evaluation (seq_number priority)
- Internal state mapping to parent states
- Confidence scoring for AI suggestions

### Multi-Agent Architecture
- Specialized agents for each scenario
- Orchestrator for coordination
- Context sharing between agents

See `AI_IMPROVEMENTS.md` for detailed AI enhancement strategies.

## Project Structure
```
recon-analysis-bot/
├── README.md
├── requirements.txt
├── config/
│   └── config.toml              # Trino, Ollama, Slack configs
├── src/
│   ├── __init__.py
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── slack_bot.py          # Main Slack bot handler
│   │   └── commands.py           # Command handlers
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── recon_analyser_agent.py  # AI-powered analysis agent (Ollama)
│   │   ├── rule_analyzer.py     # Rule matching analysis
│   │   ├── gap_analyzer.py      # Analyze missing data scenarios
│   │   └── report_parser.py    # Parse ART reports
│   ├── data/
│   │   ├── __init__.py
│   │   ├── trino_client.py      # Trino client for Querybook/datalake
│   │   ├── workspace_fetcher.py # Fetch workspace info from Trino
│   │   ├── filetype_fetcher.py  # Fetch file_type info from Trino
│   │   ├── rules_fetcher.py     # Fetch rules from rules table
│   │   ├── rule_recon_state_map_fetcher.py  # Fetch rule mappings
│   │   └── record_fetcher.py    # Fetch records from hudi tables
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ollama_service.py    # Ollama LLM integration
│   │   └── slack_service.py     # Slack message formatting
│   └── utils/
│       ├── __init__.py
│       └── query_builder.py     # Build Trino queries
└── tests/
    └── __init__.py
```

## Phase 1: Foundation Setup (Day 1 - Morning)

### 1.1 Project Setup
- Create `recon-analysis-bot/` folder structure
- Set up Python virtual environment
- Install dependencies: `slack-sdk`, `flask`, `requests`, `pandas`, `trino`, `ollama`
- Create configuration file for Trino, Ollama, and Slack settings

### 1.2 Slack Bot Integration
- Set up Slack App in workspace
- Implement basic Slack event listener using Flask
- Create command handler for `/recon-analyze` command
- Parse input: workspace_name and report attachment/URL

### 1.3 Trino Client Setup
- Create `TrinoClient` class based on existing recon implementation
- Configure Trino connection (host, port, catalog, schema)
- Implement query execution with error handling
- Set up connection to Querybook/datalake via Trino
- Reference: `recon/app/providers/trino/trino_client.py`

## Phase 2: Data Fetching via Trino (Day 1 - Afternoon)

### 2.1 Report Parser
- Parse ART report (CSV/Excel format) to extract:
  - Transaction dates
  - Record IDs
  - Recon status
  - Art remarks
- Handle both file upload and URL-based reports

### 2.2 Workspace Fetcher
- Query `workspaces` table via Trino (note: table name is plural):
  ```sql
  SELECT 
    id,
    merchant_id,
    name,
    workspace_metadata,
    reporting_emails,
    email_cut_off_time,
    automatic_fetching,
    migrated_to_hudi
  FROM workspaces 
  WHERE name = '{workspace_name}'
  AND deleted_at IS NULL
  ```
- Get workspace_id, merchant_id, workspace metadata
- Cache workspace information for subsequent queries
- Key fields: `id` (workspace_id), `merchant_id`, `name`, `workspace_metadata` (jsonb)

### 2.3 FileType Fetcher
- Query `file_types` table via Trino (note: table name uses underscore):
  ```sql
  SELECT 
    id,
    workspace_id,
    merchant_id,
    source_id,
    name,
    schema,
    file_metadata,
    validators,
    transformations,
    recon_pivot_metadata,
    source_category
  FROM file_types 
  WHERE workspace_id = '{workspace_id}'
  AND deleted_at IS NULL
  ```
- Get file_type_id, schema, transformations
- Extract `unique_column` from `file_metadata` jsonb field
- Extract other metadata from `file_metadata` jsonb (e.g., `include_columns`, `is_header_present`, `mode_column`, `hudi_record_key`)
- Identify internal vs MIS file types (check `source_category` or `name` patterns)

### 2.4 Rules Fetcher
- Query `rules` table via Trino:
  ```sql
  SELECT 
    id, 
    rule, 
    file_type1_id, 
    file_type2_id, 
    workspace_id, 
    merchant_id, 
    is_self_rule, 
    job_context_id,
    created_at,
    updated_at
  FROM rules 
  WHERE workspace_id = '{workspace_id}'
  AND (file_type1_id IN ({file_type_ids}) OR file_type2_id IN ({file_type_ids}))
  AND deleted_at IS NULL
  ORDER BY id
  ```
- Get individual rule definitions:
  - `id` (Integer, primary key)
  - `rule` (Text - actual rule expression)
  - `file_type1_id`, `file_type2_id`
  - `is_self_rule`, `job_context_id`
- Store rules in a dictionary by `id` for quick lookup
- Reference: `recon/app/web/models/rule.py`

### 2.5 Rule Recon State Map Fetcher
- Query `rule_recon_state_map` table via Trino with JOIN to `recon_state`:
  ```sql
  SELECT 
    rrsm.id,
    rrsm.workspace_id,
    rrsm.merchant_id,
    rrsm.rule_expression,
    rrsm.file_type1_id,
    rrsm.file_type2_id,
    rrsm.recon_state_id,
    rrsm.seq_number,
    rrsm.workflow_id,
    rrsm.job_context_id,
    rrsm.is_unreconciled_enrichment_rule,
    rs.state as recon_state,
    rs.art_remarks,
    rs.rank,
    rs.is_internal
  FROM rule_recon_state_map rrsm
  JOIN recon_state rs ON rrsm.recon_state_id = rs.id
  WHERE rrsm.workspace_id = '{workspace_id}'
  AND (
    (rrsm.file_type1_id IN ({file_type_ids}) AND rrsm.file_type2_id IN ({file_type_ids}))
    OR (rrsm.file_type1_id = rrsm.file_type2_id AND rrsm.file_type1_id IN ({file_type_ids}))
  )
  AND rrsm.deleted_at IS NULL
  ORDER BY rrsm.seq_number
  ```
- Get rule mappings between file types:
  - `rule_expression` (contains rule IDs like "1 and 2" that need resolution)
  - `recon_state_id`, `state`, `art_remarks`
  - `file_type1_id`, `file_type2_id`
  - `seq_number`, `workflow_id`, `job_context_id`
  - `is_unreconciled_enrichment_rule`
- Reference: `recon/app/web/models/rule_recon_state_map.py`

### 2.6 Rule Expression Resolver
- Implement `replace_rule_expression` logic (reference: `recon/app/web/utils/recon_payload.py:33-41`):
  ```python
  def resolve_rule_expression(rule_expression_str, rules_dict):
      """
      Replace rule IDs in expression with actual rule strings
      Example: "1 and 2" -> "(rule1_expression) and (rule2_expression)"
      
      Args:
          rule_expression_str: String like "1 and 2" or "1 or (2 and 3)"
          rules_dict: Dictionary mapping rule_id -> rule object with 'rule' field
      
      Returns:
          Resolved expression with actual rule logic
      """
      import re
      rule_ids = re.findall(r'\d+', rule_expression_str)
      rule_ids_int_list = list(map(int, rule_ids))
      
      resolved_expression = rule_expression_str
      for rule_id in rule_ids_int_list:
          if rule_id in rules_dict:
              rule_obj = rules_dict[rule_id]
              resolved_expression = resolved_expression.replace(
                  str(rule_id), 
                  f'({rule_obj["rule"]})'
              )
      return resolved_expression
  ```
- Process all rule_expressions from rule_recon_state_map
- Create final rule mapping with resolved expressions for AI analysis
- Handle cases where rule IDs don't exist in rules table

### 2.7 Record Fetcher
- Query Hudi tables via Trino:
  ```sql
  SELECT * FROM hudi.recon_pg_prod.{file_type_id} 
  WHERE txn_date BETWEEN '{start_date}' AND '{end_date}'
  AND {unique_column} IN ({record_ids})
  ```
- Fetch records from S3 journal using file_type_id
- Filter by unique_column and transaction dates
- Separate internal and MIS records
- Get recon_status and art_remarks from records

### 2.8 Query Builder Utility
- Create utility to build Trino queries dynamically
- Handle different file_type schemas
- Support filtering by unique_column, txn_date, recon_status
- Build queries for workspace, filetypes, rules, rule_recon_state_map, and hudi tables

## Phase 3: AI-Powered Analysis Engine (Day 2 - Morning)

### 3.1 Ollama LLM Integration
- Set up Ollama service client
- Configure LLM model (e.g., llama3, mistral, llama3.2)
- Create enhanced prompt templates with chain-of-thought reasoning
- Implement structured JSON outputs for consistent parsing
- Add few-shot learning examples in prompts
- Implement streaming responses for real-time feedback
- Handle LLM errors and retries with exponential backoff
- Add confidence scoring for AI suggestions

### 3.2 Enhanced Prompt Engineering
- **Chain-of-Thought Prompts**: Break analysis into explicit steps
  - Step 1: Understand context (workspace, file types, rules)
  - Step 2: Analyze data (field-by-field comparison)
  - Step 3: Evaluate rules (check each rule in sequence)
  - Step 4: Root cause analysis (identify primary reason)
  - Step 5: Generate recommendations (with confidence levels)
  
- **Few-Shot Learning**: Include examples in prompts
  - Example successful reconciliations
  - Example failure patterns with solutions
  - Example art_remarks for common scenarios
  
- **Structured Outputs**: Use JSON schema for consistent parsing
  - Define output structure for each scenario
  - Parse AI responses into structured data
  - Validate output format before processing

### 3.3 Context Enrichment Module
- Gather comprehensive context for AI analysis:
  - Workspace configuration and metadata
  - File type schemas and transformations
  - Complete rule hierarchy with resolved expressions
  - Rule_recon_state_map with recon_states and art_remarks
  - Historical statistics (last 30 days)
  - Common issues and patterns
- Format context for prompt injection
- Cache context to avoid repeated queries

### 3.4 Recon Analyser Agent (AI-Powered - Enhanced)
- **Main AI Agent** that orchestrates all analyses:
  - Receives enriched context (workspace, rules, history)
  - Uses multi-step reasoning for complex cases
  - Provides natural language explanations with reasoning
  - Suggests actionable recommendations with confidence scores
  - Formats findings for Slack presentation
  - Supports both individual and batch analysis modes

### 3.5 Scenario A: Recon_at Not Updated (AI Analysis - Enhanced)
- **AI-Powered Analysis with Pattern Recognition**:
  - Query records with `recon_status = 'Reconciled'` from Hudi tables
  - Check `recon_at` field in records
  - **Batch Analysis**: Analyze all affected records together to identify patterns
  - Use AI to:
    - Identify patterns in missing recon_at updates:
      * Time-based patterns (specific dates/times)
      * Batch patterns (all records from same recon run)
      * Entity type patterns (payments vs refunds)
    - Root Cause Analysis:
      * Check timing: Is there a delay between recon and entity update?
      * Check batch processing: Did a batch job fail?
      * Check data sync: Is there a sync pipeline issue?
    - Impact Assessment:
      * How many records are affected?
      * What's the business impact?
      * Are there downstream systems affected?
    - Generate recommendations:
      * Immediate actions (manual fixes)
      * Long-term fixes (pipeline improvements)
      * Monitoring suggestions
  - Generate structured report with:
    - Pattern groups and counts
    - Root cause analysis per pattern
    - Prioritized action items
    - Confidence levels for each recommendation

### 3.6 Scenario B: Missing Internal Data (AI Analysis - Enhanced)
- **AI-Powered Analysis with Ingestion Intelligence**:
  - Compare MIS records vs internal records from Hudi tables
  - **Pattern Recognition**: Group missing records by date and identify clusters
  - Use AI to:
    - Pattern Recognition:
      * Group missing records by date
      * Identify if missing records are clustered
      * Check for ingestion failures on specific dates
    - Root Cause Analysis:
      * File upload status: Were files uploaded?
      * Ingestion status: Did ingestion jobs run?
      * Ingestion errors: Any error logs?
      * Data quality: Are files in correct format?
    - Re-ingestion Strategy:
      * Which dates need re-ingestion?
      * What files need to be re-uploaded?
      * Priority order (most critical first)
    - Prevention:
      * Suggest monitoring alerts
      * Suggest validation checks
  - Generate structured recommendations with:
    - Date-wise re-ingestion plan
    - Priority levels (High/Medium/Low)
    - File-level details for re-upload
    - Monitoring suggestions

### 3.7 Scenario C: Rule Matching Failure (AI Analysis - Enhanced)
- **AI-Powered Rule Analysis with Full Context**:
  - Fetch both internal and MIS records from Hudi tables
  - Get rule configurations from rules and rule_recon_state_map tables
  - Resolve rule expressions to get actual rule logic
  - **Batch Analysis**: Analyze multiple records together to identify common failure patterns
  - Use AI with multi-step reasoning:
    - **Step 1: Rule Evaluation**
      * Evaluate rules in sequence order (seq_number)
      * For each rule: Check if conditions are met
      * Identify which specific condition failed
      * Note expected state and art_remarks if matched
    - **Step 2: Field-by-Field Comparison**
      * Compare all fields (amount, RRN, date, etc.)
      * Identify all mismatches (not just the first one)
      * Check data quality issues (nulls, formats, etc.)
    - **Step 3: Failure Identification**
      * Which rule should have matched based on data?
      * Which specific condition in that rule failed?
      * Why did it fail? (data mismatch, data quality, timing, etc.)
    - **Step 4: Art Remarks Mapping**
      * Based on rule_recon_state_map, what art_remarks should be assigned?
      * If multiple rules could match, which has higher priority (seq_number)?
      * If internal state (is_internal=true), map to parent state's art_remarks
    - **Step 5: Confidence Assessment**
      * High: Clear rule failure, obvious mismatch
      * Medium: Some ambiguity, needs review
      * Low: Complex case, manual review recommended
  - Generate detailed structured analysis with:
    - Failed rule identification (from rule_recon_state_map)
    - Complete field-by-field comparison
    - Suggested art_remarks with reasoning (from recon_state.art_remarks)
    - Confidence level and alternative suggestions
    - Natural language explanation with reasoning chain
  - Enhanced prompt includes:
    - Resolved rule expressions with full context
    - Expected recon_state and art_remarks for each rule
    - Rule sequence and priority information
    - Internal and MIS data comparison
    - Historical patterns (if available)

**Enhanced AI Prompt for Scenario C (with Chain-of-Thought)**:
```python
RULE_FAILURE_ANALYSIS_PROMPT = """
You are an expert reconciliation analyst. Follow these steps:

Step 1: Understand the Context
- Workspace: {workspace_name}
- File Type Pair: {file_type1_name} vs {file_type2_name}
- Total Unreconciled: {unreconciled_count}

Step 2: Review Rule Configuration
Rules are evaluated in sequence order (seq_number). For each rule:
- Rule 1 (seq=1): {rule1_expression} → If matched: {state1}, {art_remarks1}
- Rule 2 (seq=2): {rule2_expression} → If matched: {state2}, {art_remarks2}
- ...

Step 3: Analyze the Record Data
Internal Data: {internal_data}
MIS Data: {mis_data}

Step 4: Field-by-Field Comparison
Compare each field:
- Amount: Internal={internal_amount} vs MIS={mis_amount} → Match: {amount_match}
- RRN/Payment ID: Internal={internal_rrn} vs MIS={mis_rrn} → Match: {rrn_match}
- Date: Internal={internal_date} vs MIS={mis_date} → Match: {date_match}
- Other fields: {other_fields}

Step 5: Evaluate Rules in Sequence
For each rule in order:
- Check if all conditions are met
- If matched: Record state and art_remarks
- If not matched: Identify which condition failed

Step 6: Determine Failure Reason
- Which rule should have matched?
- Which condition failed?
- Why did it fail? (data mismatch, quality issue, timing, etc.)

Step 7: Generate Recommendation
- Based on rule_recon_state_map, suggest art_remarks
- Consider rule priority (seq_number)
- If internal state, use parent state's art_remarks
- Provide confidence level (High/Medium/Low)

Return structured JSON:
{
  "record_id": "string",
  "rule_analysis": {
    "evaluated_rules": [...],
    "should_have_matched": {...},
    "actual_failure": {...}
  },
  "recommendations": {
    "suggested_art_remarks": "string",
    "confidence": "High|Medium|Low",
    "reasoning": "string"
  }
}
"""
```

## Phase 4: Reporting & Slack Integration (Day 2 - Afternoon)

### 4.1 AI Report Generator
- Format AI analysis results into structured reports:
  - Summary statistics (total unreconciled, by category)
  - Detailed findings for each scenario with AI explanations
  - Actionable recommendations in natural language
- Generate markdown/text format optimized for Slack

### 4.2 Slack Message Formatter
- Create rich Slack messages using blocks:
  - Header with workspace name and summary
  - Sections for each analysis scenario
  - AI-generated insights in expandable sections
  - Actionable recommendations highlighted
- Use Slack Block Kit for better formatting
- Include AI confidence indicators

### 4.3 Bot Response Handler
- Send analysis results back to Slack channel
- Handle follow-up questions (basic Q&A using AI)
- Provide links to recon dashboard (if available)
- Error handling and user-friendly messages
- Show AI processing status

## Phase 5: Integration & Testing (Day 2 - Evening)

### 5.1 End-to-End Flow
- Test complete flow:
  1. FinOps sends `/recon-analyze workspace=XXX` with report
  2. Bot fetches workspace and filetype info via Trino
  3. Bot fetches rules and rule_recon_state_map via Trino
  4. Bot resolves rule expressions
  5. Bot fetches records from Hudi tables via Trino
  6. AI agent analyzes all three scenarios with full rule context
  7. Results formatted and sent to Slack

### 5.2 Error Handling
- Handle missing workspace in Trino
- Handle invalid report format
- Handle Trino query failures gracefully
- Handle missing rules or rule_recon_state_map entries
- Handle Ollama LLM errors
- Provide helpful error messages

### 5.3 Documentation
- Create README with setup instructions
- Document Trino query patterns for all tables
- Document Ollama configuration
- Document rule expression resolution logic
- Add example commands and responses
- Create demo script

## Key Implementation Details

### Data Sources (via Trino from Datalake)

- **Workspaces Table**: Query via Trino to get workspace_id, merchant_id, metadata
  - Table: `workspaces` (note: plural)
  - Key fields: `id` (workspace_id), `merchant_id`, `name`, `workspace_metadata` (jsonb)
  - Additional fields: `reporting_emails`, `email_cut_off_time`, `automatic_fetching`, `migrated_to_hudi`
  
- **File Types Table**: Query via Trino to get file_type_id, schema, unique_column, transformations
  - Table: `file_types` (note: uses underscore)
  - Key fields: `id` (file_type_id), `workspace_id`, `merchant_id`, `source_id`, `name`
  - JSONB fields: `schema`, `file_metadata`, `validators`, `transformations`, `recon_pivot_metadata`
  - Note: `unique_column` and other metadata are stored in `file_metadata` jsonb field
  
- **Rules Table**: Query via Trino to get individual rule definitions
  - Table: `rules`
  - Key fields: 
    - `id` (Integer, primary key, auto-increment)
    - `rule` (Text - actual rule expression/logic)
    - `file_type1_id`, `file_type2_id` (VARCHAR(14))
    - `workspace_id`, `merchant_id` (VARCHAR(14))
    - `is_self_rule` (Boolean)
    - `job_context_id` (VARCHAR(14), nullable)
    - `created_at`, `updated_at` (Integer timestamps)
    - `deleted_at` (Integer, nullable - soft delete)
  
- **Rule Recon State Map Table**: Query via Trino to get rule mappings with recon states
  - Table: `rule_recon_state_map`
  - Key fields:
    - `id` (Integer, primary key)
    - `rule_expression` (Text - contains rule IDs like "1 and 2" or "1 or (2 and 3)")
    - `file_type1_id`, `file_type2_id` (VARCHAR(14))
    - `recon_state_id` (Integer, FK to recon_state)
    - `seq_number` (Integer, nullable - rule priority/sequence)
    - `workflow_id` (VARCHAR(14), nullable)
    - `job_context_id` (VARCHAR(14), nullable)
    - `is_unreconciled_enrichment_rule` (Boolean)
    - `workspace_id`, `merchant_id` (VARCHAR(14))
    - `created_at`, `updated_at`, `deleted_at` (Integer timestamps)
  - JOIN with `recon_state` to get: `state`, `art_remarks`, `rank`, `is_internal`, `parent_id`
  
- **Recon State Table**: Contains recon state definitions
  - Table: `recon_state`
  - Key fields:
    - `id` (Integer, primary key)
    - `state` (VARCHAR(255) - state name like "Reconciled", "Unreconciled", "Amount_Mismatched")
    - `rank` (Integer - priority, 1 is default, higher = terminal states)
    - `is_internal` (Boolean - if true, maps to parent state for final state)
    - `parent_id` (Integer, FK to recon_state.id, nullable - for internal states)
    - `art_remarks` (VARCHAR(255), nullable - suggested remarks for this state)
    - `workspace_id`, `merchant_id` (VARCHAR(14))
    - `created_at`, `updated_at`, `deleted_at` (Integer timestamps)
  - Note: Internal states have a parent_state that determines the final recon_status
  
- **Hudi Tables**: Query `hudi.recon_pg_prod.{file_type_id}` for records from S3 journal
  - Use unique_column for filtering
  - Filter by txn_date range
  - Get all record fields including recon_status, art_remarks
  - Example: `SELECT * FROM hudi.recon_pg_prod.EFKY5jDeXD0H41 WHERE txn_date BETWEEN '2024-01-01' AND '2024-01-31'`

### Trino Query Strategy
- All data fetched via Trino from datalake
- Use existing TrinoClient pattern from recon service
- Query structure:
  - Workspaces: `SELECT * FROM workspaces WHERE name = ? AND deleted_at IS NULL`
  - File Types: `SELECT * FROM file_types WHERE workspace_id = ? AND deleted_at IS NULL`
  - Rules: `SELECT * FROM rules WHERE workspace_id = ? AND (file_type1_id IN (...) OR file_type2_id IN (...)) AND deleted_at IS NULL`
  - Rule Recon State Map: `SELECT rrsm.*, rs.state, rs.art_remarks, rs.rank, rs.is_internal FROM rule_recon_state_map rrsm JOIN recon_state rs ON rrsm.recon_state_id = rs.id WHERE rrsm.deleted_at IS NULL AND rs.deleted_at IS NULL ...`
  - Records: `SELECT * FROM hudi.recon_pg_prod.{file_type_id} WHERE ...`
- Handle Trino connection errors gracefully
- Cache frequently accessed metadata (workspace, filetypes, rules)
- Use parameterized queries to prevent SQL injection

### Rule Expression Resolution Strategy
1. Fetch all rules for workspace and store in dictionary by `id`
2. Fetch all rule_recon_state_map entries for file_type pairs
3. For each rule_expression in rule_recon_state_map:
   - Extract rule IDs using regex: `re.findall(r'\d+', rule_expression)`
   - Look up each rule ID in rules dictionary
   - Replace rule ID with actual rule expression: `"1" -> "(actual_rule_logic)"`
   - Handle complex expressions: `"1 and 2" -> "((rule1) and (rule2))"`
4. Create resolved rule mapping with:
   - Resolved rule expression
   - Associated recon_state and art_remarks
   - Sequence number for rule priority
5. Pass resolved rules to AI for analysis

### AI Analysis Strategy

**Scenario A (recon_at missing) - AI Analysis**:
```python
# Pseudo-code with Ollama
reconciled_records = trino_client.query(
    f"SELECT * FROM hudi.recon_pg_prod.{file_type_id} "
    f"WHERE recon_status = 'Reconciled' AND txn_date BETWEEN ..."
)

prompt = f"""
Analyze these reconciled records and identify why recon_at might not be updated:
Records: {reconciled_records}

Check for patterns:
1. Records with recon_status='Reconciled' but missing recon_at
2. Timing issues between reconciliation and entity update
3. Data sync gaps

Provide analysis and suggestions in structured format.
"""

ai_analysis = ollama_service.analyze(prompt)
```

**Scenario B (missing internal) - AI Analysis**:
```python
# Pseudo-code with Ollama
mis_records = trino_client.query(
    f"SELECT * FROM hudi.recon_pg_prod.{mis_file_type_id} WHERE ..."
)
internal_records = trino_client.query(
    f"SELECT * FROM hudi.recon_pg_prod.{internal_file_type_id} WHERE ..."
)

prompt = f"""
Compare MIS records with internal records:
MIS Records: {mis_records}
Internal Records: {internal_records}

Identify:
1. MIS records with no matching internal record
2. Whether internal file ingestion might have failed
3. Suggest re-ingestion dates and reasons

Provide detailed analysis with actionable recommendations.
"""

ai_analysis = ollama_service.analyze(prompt)
```

**Scenario C (rule failure) - AI Analysis**:
```python
# Pseudo-code with Ollama
unreconciled_records = trino_client.query(
    f"SELECT * FROM hudi.recon_pg_prod.{file_type_id} "
    f"WHERE recon_status = 'Unreconciled' AND ..."
)
rules = get_rules_from_trino(workspace_id, file_type_ids)
rule_recon_state_maps = get_rule_recon_state_maps_from_trino(workspace_id, file_type_ids)
resolved_rules = resolve_rule_expressions(rule_recon_state_maps, rules)

for record in unreconciled_records:
    internal_data = get_internal_record(record)
    mis_data = get_mis_record(record)
    
    prompt = f"""
    Analyze why this record failed reconciliation:
    
    Internal Data: {internal_data}
    MIS Data: {mis_data}
    
    Applicable Rules (from rule_recon_state_map):
    {resolved_rules}
    
    For each rule:
    - Rule ID: {rule_recon_state_map_id}
    - Resolved Rule Expression: {resolved_expression}
    - Expected State if matched: {recon_state}
    - Expected art_remarks if matched: {art_remarks}
    - Sequence: {seq_number}
    
    Identify:
    1. Which rule should have matched based on the data
    2. Why the rule didn't match (field-by-field comparison)
    3. What art_remarks should be assigned based on the rule_recon_state_map configuration
    4. Explanation in natural language
    
    Provide structured analysis with field-by-field comparison.
    """
    
    ai_analysis = ollama_service.analyze(prompt)
```

## Deliverables

1. **Working Slack Bot** that responds to commands
2. **AI-Powered Analysis Agent** using Ollama LLM
3. **Trino Data Fetchers** for workspace, filetypes, rules, rule_recon_state_map, and Hudi records
4. **Rule Expression Resolver** to convert rule IDs to actual expressions
5. **Three AI Analysis Modules** for the scenarios
6. **Slack Integration** with formatted messages
7. **Documentation** for setup and usage
8. **Demo Script** showing the complete flow

## Success Criteria

- Bot can receive workspace name and report
- Bot fetches data via Trino from datalake (all required tables)
- Bot resolves rule expressions correctly
- AI agent performs all three analyses with intelligent insights
- Bot provides actionable insights in natural language via Slack
- All components work together end-to-end
- Code is well-structured and documented

## Future Enhancements (Post-Hackathon)

### AI Improvements
- Fine-tune Ollama prompts based on feedback from PSE team
- Historical pattern learning: Train on past reconciliation data
- Multi-model ensemble: Use multiple AI models for validation
- Fine-tuning: Train custom model on workspace-specific data
- Active learning: Learn from manual corrections

### Advanced Features
- Integration with txn_entity service for direct updates
- Dashboard for visualization of AI insights
- Automated re-ingestion triggers based on AI recommendations
- Rule performance analytics: Track which rules fail most often
- Predictive analysis: Predict reconciliation failures before they happen
- Anomaly detection: Identify unusual patterns automatically

### Operational Improvements
- Real-time streaming analysis for large datasets
- Batch processing optimization for performance
- Caching of AI responses for similar records
- A/B testing of different prompt strategies
- Metrics dashboard for AI accuracy and confidence

