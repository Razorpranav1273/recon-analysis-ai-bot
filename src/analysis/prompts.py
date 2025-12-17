"""
Enhanced prompts for AI-powered analysis in recon-analysis-bot
Includes chain-of-thought reasoning, few-shot examples, and structured outputs.
"""

# Enhanced ART Remarks Generation with Chain-of-Thought
ART_REMARKS_GENERATION_PROMPT = """You are an expert reconciliation analyst. Follow these steps to generate intelligent ART (Auto Reconciliation Tool) remarks.

Step 1: Understand the Context
- Review the rule expression and what it's checking
- Identify which specific condition failed
- Note the field values from both internal and MIS data

Step 2: Analyze the Mismatch
- Compare the mismatched fields side-by-side
- Determine the root cause (data quality, timing, format, etc.)
- Assess the severity (critical, moderate, minor)

Step 3: Generate Recommendation
- Create a concise remark (1-2 sentences)
- Focus on the most critical issue
- Use professional language suitable for business users
- Include actionable guidance if applicable

Given the following information:
- Failed Rule ID: {rule_id}
- Rule Expression: {rule_expression}
- Mismatch Details: {mismatch_details}
- Internal Data: {internal_data}
- MIS Data: {mis_data}

Examples of good ART remarks:
Example 1: "RRN mismatch detected: Internal RRN 'ABC123' does not match MIS RRN 'XYZ789'. Verify payment reference numbers."
Example 2: "Amount mismatch: Internal amount ₹1000.00 differs from MIS amount ₹1000.50. Check for rounding or fee differences."
Example 3: "Date mismatch: Transaction dates differ by 1 day. Verify timezone or processing delays."

Now generate the ART remark following the steps above:

ART Remark:"""

# Enhanced Rule Failure Analysis with Full Context
RULE_FAILURE_ANALYSIS_PROMPT = """You are an expert reconciliation analyst. Analyze this rule matching failure using structured reasoning.

Step 1: Understand the Rule Configuration
- Rule Expression: {rule_expression}
- Expected State if matched: {expected_state}
- Expected art_remarks if matched: {expected_art_remarks}
- Sequence Number: {seq_number} (lower = higher priority)

Step 2: Compare the Data
Internal Record:
{internal_data}

MIS Record:
{mis_data}

Step 3: Evaluate Each Condition
For each condition in the rule:
- Check if the condition is met
- If not met, identify which field/value caused the failure
- Note the difference (if applicable)

Step 4: Determine Root Cause
- Why did the rule fail? (data mismatch, quality issue, timing, format, etc.)
- Is this a systematic issue or one-off?
- What's the most likely explanation?

Step 5: Generate Analysis
Provide your analysis in this JSON format:
{{
  "rule_evaluation": {{
    "rule_id": "{rule_id}",
    "matched": false,
    "failed_condition": "description of what failed",
    "field_mismatches": {{
      "field_name": {{
        "internal_value": "value",
        "mis_value": "value",
        "difference": "explanation"
      }}
    }}
  }},
  "root_cause": "explanation of why it failed",
  "recommendations": {{
    "suggested_art_remarks": "your suggested remark",
    "confidence": "High|Medium|Low",
    "reasoning": "why this remark is appropriate",
    "next_steps": ["action 1", "action 2"]
  }}
}}

Now analyze this failure:

Rule: {rule_expression}
Internal: {internal_data}
MIS: {mis_data}
"""

# Few-Shot Examples for Rule Analysis
RULE_ANALYSIS_FEW_SHOT_EXAMPLES = """
Example 1 - Successful Match:
Internal: {{"amount": 1000, "rrn": "ABC123", "date": "2024-01-01"}}
MIS: {{"amount": 1000, "rrn": "ABC123", "date": "2024-01-01"}}
Rule: "amount == mis_amount AND rrn == mis_rrn"
Result: ✅ MATCHED → State: "Reconciled", art_remarks: null

Example 2 - RRN Mismatch:
Internal: {{"amount": 1000, "rrn": "ABC123", "date": "2024-01-01"}}
MIS: {{"amount": 1000, "rrn": "XYZ789", "date": "2024-01-01"}}
Rule: "amount == mis_amount AND rrn == mis_rrn"
Result: ❌ FAILED → Condition "rrn == mis_rrn" failed
        → State: "RRN_Mismatch", art_remarks: "RRN mismatch: Internal 'ABC123' vs MIS 'XYZ789'. Verify payment reference."

Example 3 - Amount Mismatch:
Internal: {{"amount": 1000.00, "rrn": "ABC123", "date": "2024-01-01"}}
MIS: {{"amount": 1000.50, "rrn": "ABC123", "date": "2024-01-01"}}
Rule: "amount == mis_amount AND rrn == mis_rrn"
Result: ❌ FAILED → Condition "amount == mis_amount" failed (difference: 0.50)
        → State: "Amount_Mismatch", art_remarks: "Amount mismatch: ₹0.50 difference. Check for fees or rounding."
"""

# Enhanced Analysis Explanation with Context
ANALYSIS_EXPLANATION_PROMPT = """You are an expert reconciliation analyst. Explain this finding clearly for business users.

Context:
- Finding Type: {finding_type}
- Issue: {issue}
- Details: {details}
- Impact: {impact}

Provide a clear explanation (2-3 sentences) that:
1. Explains what the issue means in business terms
2. Why it matters (business impact)
3. What the recommended action is

Use simple, non-technical language where possible.

Explanation:"""

# Batch Pattern Recognition Prompt
BATCH_PATTERN_ANALYSIS_PROMPT = """You are an expert reconciliation analyst. Analyze these {count} unreconciled records together to identify patterns.

Records:
{records_json}

Tasks:
1. Group records by failure type (amount mismatch, RRN mismatch, date mismatch, missing data, etc.)
2. Identify common patterns:
   - Are failures concentrated on specific dates?
   - Are certain file types more prone to failures?
   - Are there systematic data quality issues?
3. For each pattern group:
   - Identify root cause
   - Suggest bulk remediation steps
   - Estimate impact (number of records affected)

Return your analysis in this JSON format:
{{
  "patterns": [
    {{
      "pattern_name": "string",
      "failure_type": "string",
      "record_count": "integer",
      "common_characteristics": ["string"],
      "root_cause": "string",
      "bulk_recommendations": ["string"],
      "affected_record_ids": ["string"]
    }}
  ],
  "summary": {{
    "total_patterns": "integer",
    "most_common_failure": "string",
    "recommended_priority": "High|Medium|Low"
  }}
}}

Analyze the records now:
"""

