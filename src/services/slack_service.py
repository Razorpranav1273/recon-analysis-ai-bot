"""
Slack Service for Message Formatting
Formats analysis results into Slack Block Kit messages.
Uses AI for intelligent analysis explanations.
"""

from typing import Dict, Any, List, Optional
from src.utils.logging import logger
from src.utils.llm_utils import (
    create_langchain_azure_chat_openai,
    create_ollama_llm,
    invoke_with_retry_langchain,
)
from src.utils.config_reader import get_config_value
from src.analysis.prompts import ANALYSIS_EXPLANATION_PROMPT
from langchain_core.messages import HumanMessage


class SlackService:
    """
    Service for formatting analysis results into Slack messages.
    Uses AI for intelligent analysis explanations.
    """

    def __init__(self):
        """Initialize Slack service with optional LLM."""
        self.llm = None
        self._init_llm()

    def _init_llm(self):
        """Initialize LLM for AI-powered explanations (Ollama or Azure OpenAI)."""
        # Try Ollama first (local, free, open source)
        ollama_enabled = get_config_value("ollama.enabled", False)
        if ollama_enabled:
            try:
                base_url = get_config_value("ollama.base_url", "http://localhost:11434")
                model = get_config_value("ollama.model", "llama2")
                self.llm = create_ollama_llm(model_name=model, base_url=base_url)
                logger.info("Ollama LLM initialized for Slack service", model=model)
                return
            except Exception as e:
                logger.warning(f"Failed to initialize Ollama, trying Azure OpenAI: {e}")

        # Fallback to Azure OpenAI if Ollama not available
        try:
            self.llm = create_langchain_azure_chat_openai()
            logger.info("Azure OpenAI LLM initialized for Slack service")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM, will use basic formatting: {e}")
            self.llm = None

    def format_analysis_report(self, analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Format analysis results into Slack Block Kit message blocks.

        Args:
            analysis_results: Dict containing results from all three analyzers

        Returns:
            List of Slack Block Kit blocks
        """
        try:
            workspace_name = analysis_results.get("workspace_name", "Unknown")
            workspace_id = analysis_results.get("workspace_id", "")

            blocks = []

            # Header block
            blocks.append({
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Recon Analysis Report: {workspace_name}",
                    "emoji": True,
                },
            })

            # Summary section
            summary_blocks = self._create_summary_section(analysis_results)
            blocks.extend(summary_blocks)

            # Scenario A: Recon_at not updated
            scenario_a = analysis_results.get("scenario_a")
            if scenario_a and scenario_a.get("findings"):
                blocks.extend(self._format_scenario_a(scenario_a))

            # Scenario B: Missing internal data
            scenario_b = analysis_results.get("scenario_b")
            if scenario_b and scenario_b.get("findings"):
                blocks.extend(self._format_scenario_b(scenario_b))

            # Scenario C: Rule matching failures
            scenario_c = analysis_results.get("scenario_c")
            if scenario_c and scenario_c.get("findings"):
                blocks.extend(self._format_scenario_c(scenario_c))

            # Footer with timestamp
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Analysis completed at {analysis_results.get('timestamp', 'N/A')}",
                    }
                ],
            })

            return blocks

        except Exception as e:
            logger.error("Failed to format analysis report", error=str(e))
            return self._create_error_message(str(e))

    def _create_summary_section(self, analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create summary section with statistics."""
        blocks = []

        # Summary divider
        blocks.append({"type": "divider"})

        # Summary text - handle both old and new format
        scenario_a = analysis_results.get("scenario_a") or {}
        scenario_b = analysis_results.get("scenario_b") or {}
        scenario_c = analysis_results.get("scenario_c") or {}
        
        # New unified format has "count" key, old format has specific keys
        if isinstance(scenario_a, dict) and "count" in scenario_a:
            scenario_a_count = scenario_a.get("count", 0)
        elif isinstance(scenario_a, dict):
            scenario_a_count = scenario_a.get("needs_update", 0)
        else:
            scenario_a_count = 0
            
        if isinstance(scenario_b, dict) and "count" in scenario_b:
            scenario_b_count = scenario_b.get("count", 0)
        elif isinstance(scenario_b, dict):
            scenario_b_count = scenario_b.get("missing_internal", 0)
        else:
            scenario_b_count = 0
            
        if isinstance(scenario_c, dict) and "count" in scenario_c:
            scenario_c_count = scenario_c.get("count", 0)
        elif isinstance(scenario_c, dict):
            scenario_c_count = scenario_c.get("rule_failures", 0)
        else:
            scenario_c_count = 0
            
        total_issues = scenario_a_count + scenario_b_count + scenario_c_count

        # Generate AI-powered summary explanation if LLM is available
        summary_explanation = ""
        if self.llm and total_issues > 0:
            try:
                summary_explanation = self._generate_summary_explanation(
                    scenario_a_count, scenario_b_count, scenario_c_count, total_issues
                )
            except Exception as e:
                logger.warning(f"Failed to generate AI summary: {e}")

        summary_text = f"""
*Summary Statistics:*

• *Scenario A (recon_at not updated):* {scenario_a_count} records
• *Scenario B (missing internal data):* {scenario_b_count} records
• *Scenario C (rule matching failures):* {scenario_c_count} records

*Total Issues Found:* {total_issues}
        """.strip()

        if summary_explanation:
            summary_text += f"\n\n*AI Analysis:*\n{summary_explanation}"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": summary_text,
            },
        })

        return blocks

    def _format_scenario_a(self, scenario_a: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format Scenario A findings."""
        blocks = []

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Scenario A: recon_at Not Updated*",
            },
        })

        findings = scenario_a.get("findings", [])[:10]  # Limit to 10 for display

        for finding in findings:
            entity_id = finding.get("entity_id", "N/A")
            file_type_id = finding.get("file_type_id", "N/A")
            suggestion = finding.get("suggestion", "No suggestion provided")

            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Entity ID:*\n{entity_id}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*File Type ID:*\n{file_type_id}",
                    },
                ],
            })

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Suggestion:* {suggestion}",
                },
            })

        if len(scenario_a.get("findings", [])) > 10:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"... and {len(scenario_a.get('findings', [])) - 10} more findings",
                    }
                ],
            })

        return blocks

    def _format_scenario_b(self, scenario_b: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format Scenario B findings."""
        blocks = []

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Scenario B: Missing Internal Data*",
            },
        })

        findings = scenario_b.get("findings", [])[:10]  # Limit to 10 for display

        for finding in findings:
            entity_id = finding.get("entity_id", "N/A")
            txn_date = finding.get("transaction_date", "N/A")
            issue = finding.get("issue", "N/A")
            suggestion = finding.get("suggestion", "No suggestion provided")

            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Entity ID:*\n{entity_id}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Issue:*\n{issue}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Transaction Date:*\n{txn_date}",
                    },
                ],
            })

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Suggestion:* {suggestion}",
                },
            })

        if len(scenario_b.get("findings", [])) > 10:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"... and {len(scenario_b.get('findings', [])) - 10} more findings",
                    }
                ],
            })

        return blocks

    def _format_scenario_c(self, scenario_c: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format Scenario C findings."""
        blocks = []

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Scenario C: Rule Matching Failures*",
            },
        })

        findings = scenario_c.get("findings", [])[:10]  # Limit to 10 for display

        for finding in findings:
            entity_id = finding.get("entity_id", "N/A")
            rule_id = finding.get("failed_rule_id", "N/A")
            rule_expression = finding.get("failed_rule_expression", "N/A")
            art_remarks = finding.get("suggested_art_remarks", "")
            mismatch_details = finding.get("mismatch_details", {})

            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Entity ID:*\n{entity_id}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Failed Rule ID:*\n{rule_id}",
                    },
                ],
            })

            if mismatch_details:
                mismatch_text = "\n".join([f"• {k}: {v}" for k, v in mismatch_details.items()])
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Mismatch Details:*\n{mismatch_text}",
                    },
                })

            if art_remarks:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Suggested ART Remarks:* {art_remarks}",
                    },
                })

        if len(scenario_c.get("findings", [])) > 10:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"... and {len(scenario_c.get('findings', [])) - 10} more findings",
                    }
                ],
            })

        return blocks

    def _generate_summary_explanation(
        self, scenario_a: int, scenario_b: int, scenario_c: int, total: int
    ) -> str:
        """Generate AI-powered summary explanation."""
        prompt = f"""Provide a brief 2-3 sentence explanation of these reconciliation issues:
- {scenario_a} records need recon_at timestamp updates
- {scenario_b} records are missing internal data
- {scenario_c} records have rule matching failures
Total: {total} issues

Explain what this means and the overall impact in business terms."""

        try:
            # Both Ollama (ChatOllama) and Azure OpenAI use the same message interface
            messages = [HumanMessage(content=prompt)]
            result = invoke_with_retry_langchain(
                self.llm, messages, operation="generate_summary_explanation"
            )
            if hasattr(result, "content"):
                return result.content.strip()
            return str(result).strip()
        except Exception as e:
            logger.warning(f"AI summary generation failed: {e}")
            return ""

    def _create_error_message(self, error: str) -> List[Dict[str, Any]]:
        """Create error message block."""
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error:* {error}",
                },
            }
        ]

    def format_simple_message(self, text: str) -> Dict[str, Any]:
        """
        Format a simple text message.

        Args:
            text: Message text

        Returns:
            Slack message dict
        """
        return {
            "response_type": "ephemeral",
            "text": text,
        }

