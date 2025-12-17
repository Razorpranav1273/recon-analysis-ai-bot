"""
Prompts for AI-powered analysis in recon-analysis-bot
"""

ART_REMARKS_GENERATION_PROMPT = """You are an expert reconciliation analyst. Your task is to generate intelligent ART (Auto Reconciliation Tool) remarks based on rule matching failures.

Given the following information:
- Failed Rule ID: {rule_id}
- Rule Expression: {rule_expression}
- Mismatch Details: {mismatch_details}
- Internal Data: {internal_data}
- MIS Data: {mis_data}

Generate a concise, actionable ART remark that:
1. Clearly explains what failed
2. Provides context about the mismatch
3. Suggests what action should be taken
4. Is professional and suitable for business users

The remark should be 1-2 sentences maximum and focus on the most critical issue.

ART Remark:"""

ANALYSIS_EXPLANATION_PROMPT = """You are an expert reconciliation analyst. Explain the following reconciliation analysis finding in a clear, concise manner for business users.

Finding Type: {finding_type}
Issue: {issue}
Details: {details}

Provide a brief explanation (2-3 sentences) that:
1. Explains what the issue means
2. Why it matters
3. What the recommended action is

Explanation:"""

