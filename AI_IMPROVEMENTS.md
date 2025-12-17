# AI Utilization Improvements for Recon Analysis Bot

## Current State Analysis

### Existing Implementation
- Basic AI integration with Ollama/Azure OpenAI
- Simple prompt templates for ART remarks generation
- Per-record analysis (one-by-one)
- Limited context in prompts
- No pattern recognition across records
- No structured output parsing

### Opportunities for Improvement
1. **Multi-Step Reasoning**: Break complex analysis into steps
2. **Batch Processing**: Analyze multiple records together for pattern recognition
3. **Context Enrichment**: Include historical patterns, workspace configs, rule hierarchies
4. **Structured Outputs**: Use JSON mode for consistent parsing
5. **Chain-of-Thought**: Make AI reasoning explicit
6. **Few-Shot Learning**: Include examples in prompts
7. **Rule-Aware Analysis**: Better integration with rule_recon_state_map
8. **Confidence Scoring**: AI provides confidence levels for suggestions

## Enhanced AI Architecture

### 1. Multi-Agent System

Instead of single AI calls, use specialized agents:

```
┌─────────────────────────────────────────────────────────┐
│              Recon Analysis Orchestrator                 │
│              (Main AI Agent)                             │
└──────────────┬──────────────────────────────────────────┘
               │
       ┌───────┴────────┬──────────────┬──────────────┐
       │                │              │              │
┌──────▼──────┐  ┌──────▼──────┐  ┌───▼──────┐  ┌───▼──────┐
│ Pattern     │  │ Rule        │  │ Gap      │  │ Status   │
│ Recognition │  │ Evaluator   │  │ Analyzer │  │ Checker  │
│ Agent       │  │ Agent       │  │ Agent    │  │ Agent    │
└─────────────┘  └─────────────┘  └──────────┘  └──────────┘
```

### 2. Enhanced Prompt Engineering

#### A. Chain-of-Thought Prompts

**Current Approach:**
```
"Analyze why this record failed reconciliation..."
```

**Improved Approach:**
```
You are an expert reconciliation analyst. Follow these steps:

Step 1: Understand the Context
- Review the workspace configuration
- Understand the file types involved
- Review the rule hierarchy

Step 2: Analyze the Data
- Compare internal vs MIS data field-by-field
- Identify all mismatches (not just the first one)
- Check data quality issues

Step 3: Evaluate Rules
- For each applicable rule in sequence:
  * Check if rule conditions are met
  * Identify which specific condition failed
  * Note the expected state and art_remarks if matched

Step 4: Root Cause Analysis
- Determine the primary reason for failure
- Identify contributing factors
- Check for data quality issues

Step 5: Generate Recommendations
- Suggest appropriate art_remarks based on rule_recon_state_map
- Provide actionable next steps
- Estimate confidence level (High/Medium/Low)

Now analyze this record:
[Record data and rules]
```

#### B. Few-Shot Learning Prompts

Include examples in prompts:

```
Example 1:
Internal: {amount: 1000, rrn: "ABC123", date: "2024-01-01"}
MIS: {amount: 1000, rrn: "ABC123", date: "2024-01-01"}
Rule: "amount == mis_amount AND rrn == mis_rrn"
Result: ✅ MATCHED → State: "Reconciled", art_remarks: null

Example 2:
Internal: {amount: 1000, rrn: "ABC123", date: "2024-01-01"}
MIS: {amount: 1000, rrn: "XYZ789", date: "2024-01-01"}
Rule: "amount == mis_amount AND rrn == mis_rrn"
Result: ❌ FAILED → Condition "rrn == mis_rrn" failed
        → State: "RRN_Mismatch", art_remarks: "RRN mismatch detected"

Now analyze:
[Actual record data]
```

#### C. Structured Output Prompts

Use JSON schema for consistent parsing:

```python
STRUCTURED_ANALYSIS_PROMPT = """
Analyze this reconciliation failure and return a JSON object with this exact structure:

{
  "record_id": "string",
  "analysis": {
    "primary_failure_reason": "string",
    "failed_conditions": [
      {
        "condition": "string",
        "internal_value": "any",
        "mis_value": "any",
        "rule_id": "integer"
      }
    ],
    "applicable_rules": [
      {
        "rule_id": "integer",
        "rule_expression": "string",
        "evaluated": "boolean",
        "matched": "boolean",
        "expected_state": "string",
        "expected_art_remarks": "string"
      }
    ]
  },
  "recommendations": {
    "suggested_art_remarks": "string",
    "confidence": "High|Medium|Low",
    "reasoning": "string",
    "next_steps": ["string"]
  }
}

Record Data:
{record_data}
"""
```

### 3. Batch Pattern Recognition

Instead of analyzing records one-by-one, analyze in batches:

```python
BATCH_PATTERN_ANALYSIS_PROMPT = """
Analyze these {count} unreconciled records together to identify patterns:

Records:
{records_json}

Tasks:
1. Group records by failure type (amount mismatch, RRN mismatch, date mismatch, etc.)
2. Identify common patterns:
   - Are failures concentrated on specific dates?
   - Are certain file types more prone to failures?
   - Are there systematic data quality issues?
3. For each pattern group:
   - Identify root cause
   - Suggest bulk remediation steps
   - Estimate impact (number of records affected)

Return structured analysis:
{
  "patterns": [
    {
      "pattern_name": "string",
      "failure_type": "string",
      "record_count": "integer",
      "common_characteristics": ["string"],
      "root_cause": "string",
      "bulk_recommendations": ["string"],
      "affected_record_ids": ["string"]
    }
  ],
  "summary": {
    "total_patterns": "integer",
    "most_common_failure": "string",
    "recommended_priority": "High|Medium|Low"
  }
}
"""
```

### 4. Enhanced Scenario-Specific Prompts

#### Scenario A: Recon_at Not Updated

**Improved Prompt:**
```python
RECON_AT_ANALYSIS_PROMPT = """
You are analyzing reconciliation timestamp synchronization issues.

Context:
- Workspace: {workspace_name}
- Total reconciled records: {total_count}
- Records with recon_at in recon_result: {with_recon_at_count}
- Records missing recon_at in txn_entity: {missing_count}

Analysis Tasks:
1. Identify patterns in missing recon_at updates:
   - Time-based patterns (specific dates/times)
   - Batch patterns (all records from same recon run)
   - Entity type patterns (payments vs refunds)
   
2. Root Cause Analysis:
   - Check timing: Is there a delay between recon and entity update?
   - Check batch processing: Did a batch job fail?
   - Check data sync: Is there a sync pipeline issue?
   
3. Impact Assessment:
   - How many records are affected?
   - What's the business impact?
   - Are there downstream systems affected?

4. Recommendations:
   - Immediate actions (manual fixes)
   - Long-term fixes (pipeline improvements)
   - Monitoring suggestions

Records Data:
{records_data}

Provide structured analysis with actionable recommendations.
"""
```

#### Scenario B: Missing Internal Data

**Improved Prompt:**
```python
MISSING_INTERNAL_DATA_PROMPT = """
You are analyzing missing internal data for MIS records.

Context:
- Workspace: {workspace_name}
- Date Range: {start_date} to {end_date}
- MIS Records: {mis_count}
- Internal Records: {internal_count}
- Missing Internal: {missing_count}

Analysis Tasks:
1. Pattern Recognition:
   - Group missing records by date
   - Identify if missing records are clustered
   - Check for ingestion failures on specific dates
   
2. Root Cause Analysis:
   - File upload status: Were files uploaded?
   - Ingestion status: Did ingestion jobs run?
   - Ingestion errors: Any error logs?
   - Data quality: Are files in correct format?
   
3. Re-ingestion Strategy:
   - Which dates need re-ingestion?
   - What files need to be re-uploaded?
   - Priority order (most critical first)
   
4. Prevention:
   - Suggest monitoring alerts
   - Suggest validation checks

MIS Records Missing Internal:
{missing_records}

Ingestion History:
{ingestion_history}

Provide structured recommendations with priority levels.
"""
```

#### Scenario C: Rule Matching Failure (Enhanced)

**Improved Prompt:**
```python
RULE_FAILURE_ANALYSIS_PROMPT = """
You are analyzing rule matching failures for unreconciled records.

Context:
- Workspace: {workspace_name}
- File Type Pair: {file_type1_name} vs {file_type2_name}
- Total Unreconciled: {unreconciled_count}
- Records with Both Data: {with_both_count}

Rule Configuration:
{resolved_rules_with_states}

Analysis Process:

Step 1: Rule Evaluation
For each record, evaluate rules in sequence order (seq_number):
- Rule 1 (seq=1): {rule1_expression} → If matched: {state1}, {art_remarks1}
- Rule 2 (seq=2): {rule2_expression} → If matched: {state2}, {art_remarks2}
- ...

Step 2: Field-by-Field Comparison
For each record, compare:
- Amount: Internal={internal_amount} vs MIS={mis_amount}
- RRN/Payment ID: Internal={internal_rrn} vs MIS={mis_rrn}
- Date: Internal={internal_date} vs MIS={mis_date}
- Other fields: {other_fields}

Step 3: Failure Identification
- Which rule should have matched based on data?
- Which specific condition in that rule failed?
- Why did it fail? (data mismatch, data quality, timing, etc.)

Step 4: Art Remarks Mapping
- Based on rule_recon_state_map, what art_remarks should be assigned?
- If multiple rules could match, which has higher priority (seq_number)?
- If internal state (is_internal=true), map to parent state's art_remarks

Step 5: Confidence Assessment
- High: Clear rule failure, obvious mismatch
- Medium: Some ambiguity, needs review
- Low: Complex case, manual review recommended

Record Data:
{record_data}

Return structured analysis:
{
  "record_id": "string",
  "rule_analysis": {
    "evaluated_rules": [
      {
        "rule_id": "integer",
        "rule_recon_state_map_id": "integer",
        "seq_number": "integer",
        "resolved_expression": "string",
        "matched": "boolean",
        "failed_condition": "string",
        "expected_state": "string",
        "expected_art_remarks": "string"
      }
    ],
    "should_have_matched": {
      "rule_id": "integer",
      "reason": "string"
    },
    "actual_failure": {
      "primary_reason": "string",
      "failed_conditions": ["string"],
      "field_mismatches": {
        "field_name": {
          "internal": "value",
          "mis": "value",
          "difference": "value"
        }
      }
    }
  },
  "recommendations": {
    "suggested_art_remarks": "string",
    "confidence": "High|Medium|Low",
    "reasoning": "string",
    "alternative_remarks": ["string"],
    "next_steps": ["string"]
  }
}
"""
```

### 5. Historical Pattern Learning

Use AI to learn from historical data:

```python
HISTORICAL_PATTERN_PROMPT = """
Analyze historical reconciliation patterns for workspace {workspace_name}.

Historical Data (Last 30 days):
- Total Records: {total_historical}
- Reconciled: {reconciled_historical}
- Unreconciled: {unreconciled_historical}
- Common Failure Types: {failure_types}

Current Issue:
{current_issue}

Tasks:
1. Compare current issue with historical patterns
2. Identify if this is a recurring issue
3. Check if similar issues were resolved before
4. Suggest solutions based on historical fixes

Provide insights on:
- Is this a new issue or recurring?
- What worked before for similar issues?
- What's different this time?
"""
```

### 6. Multi-Model Ensemble

Use multiple AI models for validation:

```python
def ensemble_analysis(record_data, rules):
    """
    Get analysis from multiple models and combine results.
    """
    # Primary model (Ollama)
    ollama_result = ollama_llm.analyze(record_data, rules)
    
    # Validation model (if available)
    if azure_llm_available:
        azure_result = azure_llm.analyze(record_data, rules)
        
        # Compare and reconcile
        if ollama_result.confidence == "High" and azure_result.confidence == "High":
            if ollama_result.suggested_remarks == azure_result.suggested_remarks:
                return ollama_result  # High confidence, both agree
            else:
                # Disagreement - flag for review
                return {
                    "suggested_remarks": ollama_result.suggested_remarks,
                    "confidence": "Medium",
                    "alternative": azure_result.suggested_remarks,
                    "needs_review": True
                }
    
    return ollama_result
```

### 7. Context Enrichment

Enrich prompts with additional context:

```python
def enrich_prompt_context(workspace_id, file_type_ids):
    """
    Gather all relevant context for AI analysis.
    """
    context = {
        "workspace": fetch_workspace(workspace_id),
        "file_types": fetch_file_types(file_type_ids),
        "rules": fetch_rules(workspace_id, file_type_ids),
        "rule_recon_state_map": fetch_rule_recon_state_map(workspace_id, file_type_ids),
        "recon_states": fetch_recon_states(workspace_id),
        "historical_stats": fetch_historical_stats(workspace_id, days=30),
        "common_issues": fetch_common_issues(workspace_id),
    }
    
    return format_context_for_prompt(context)
```

### 8. Streaming Responses for Real-Time Feedback

For long-running analyses, stream progress:

```python
async def stream_analysis(records, rules):
    """
    Stream AI analysis progress for better UX.
    """
    yield "Starting analysis of {len(records)} records...\n"
    
    for i, record in enumerate(records):
        yield f"Analyzing record {i+1}/{len(records)}...\n"
        
        analysis = await ai_analyze(record, rules)
        
        yield f"✓ Record {i+1}: {analysis.summary}\n"
        
        if analysis.confidence == "Low":
            yield "⚠ Low confidence - manual review recommended\n"
    
    yield "\nGenerating summary...\n"
    summary = await generate_summary(all_analyses)
    yield summary
```

## Implementation Plan

### Phase 1: Enhanced Prompts (Day 1)
1. ✅ Update prompt templates with chain-of-thought
2. ✅ Add few-shot examples
3. ✅ Implement structured JSON outputs
4. ✅ Add confidence scoring

### Phase 2: Batch Processing (Day 1-2)
1. ✅ Implement batch pattern recognition
2. ✅ Add grouping logic for similar failures
3. ✅ Create bulk recommendation generator

### Phase 3: Context Enrichment (Day 2)
1. ✅ Gather workspace/file_type/rules context
2. ✅ Include historical patterns
3. ✅ Add rule_recon_state_map integration

### Phase 4: Multi-Agent System (Day 2)
1. ✅ Create specialized agent classes
2. ✅ Implement orchestrator
3. ✅ Add agent coordination logic

### Phase 5: Advanced Features (Post-Hackathon)
1. Historical pattern learning
2. Multi-model ensemble
3. Streaming responses
4. Fine-tuning on historical data

## Example: Enhanced Rule Analyzer

```python
class EnhancedRuleAnalyzer:
    """
    Enhanced rule analyzer with advanced AI capabilities.
    """
    
    def __init__(self):
        self.llm = create_ollama_llm()
        self.context_enricher = ContextEnricher()
        self.pattern_recognizer = PatternRecognizer()
    
    async def analyze_batch(self, records, workspace_id, file_type_ids):
        """
        Analyze multiple records together for pattern recognition.
        """
        # Step 1: Enrich context
        context = self.context_enricher.enrich(workspace_id, file_type_ids)
        
        # Step 2: Batch analysis
        batch_prompt = BATCH_PATTERN_ANALYSIS_PROMPT.format(
            count=len(records),
            records_json=json.dumps(records, indent=2),
            context=context
        )
        
        batch_analysis = await self.llm.analyze(batch_prompt)
        
        # Step 3: Individual record analysis with context
        detailed_analyses = []
        for record in records:
            detailed = await self.analyze_record_with_context(
                record, context, batch_analysis
            )
            detailed_analyses.append(detailed)
        
        # Step 4: Generate recommendations
        recommendations = self.generate_recommendations(
            batch_analysis, detailed_analyses
        )
        
        return {
            "batch_patterns": batch_analysis,
            "individual_analyses": detailed_analyses,
            "recommendations": recommendations
        }
    
    async def analyze_record_with_context(self, record, context, batch_analysis):
        """
        Analyze individual record with full context.
        """
        prompt = RULE_FAILURE_ANALYSIS_PROMPT.format(
            record_data=json.dumps(record, indent=2),
            resolved_rules=context["resolved_rules"],
            batch_context=batch_analysis.get("patterns", [])
        )
        
        analysis = await self.llm.analyze_structured(prompt)
        return analysis
```

## Success Metrics

1. **Accuracy**: AI suggestions match manual PSE analysis (target: >80%)
2. **Confidence**: High confidence suggestions are correct (target: >90%)
3. **Coverage**: AI analyzes all three scenarios effectively
4. **Speed**: Batch processing reduces analysis time (target: 10x faster)
5. **Actionability**: Recommendations lead to successful fixes (target: >70%)

## Next Steps

1. Review and approve enhanced prompt templates
2. Implement context enrichment module
3. Add batch processing capabilities
4. Test with real data from stage environment
5. Iterate based on feedback

