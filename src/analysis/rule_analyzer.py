"""
Rule Analyzer (Scenario C)
Analyzes rule matching failures for unreconciled records.
Uses AI to generate intelligent art_remarks suggestions.
"""

from typing import Dict, Any, List, Optional, Tuple
from src.analysis.data_fetcher import DataFetcher
from src.utils.logging import logger
from src.utils.llm_utils import (
    create_langchain_azure_chat_openai,
    create_ollama_llm,
    invoke_with_retry_langchain,
)
from src.utils.config_reader import get_config_value
from src.analysis.prompts import ART_REMARKS_GENERATION_PROMPT
from langchain_core.messages import HumanMessage


class RuleAnalyzer:
    """
    Analyzer for Scenario C: Rule matching failures.
    Uses AI to generate intelligent art_remarks suggestions.
    """

    def __init__(self):
        """Initialize rule analyzer."""
        self.data_fetcher = DataFetcher()
        self.llm = None
        self._init_llm()

    def _init_llm(self):
        """Initialize LLM for AI-powered suggestions (Ollama or Azure OpenAI)."""
        # Try Ollama first (local, free, open source)
        ollama_enabled = get_config_value("ollama.enabled", False)
        if ollama_enabled:
            try:
                base_url = get_config_value("ollama.base_url", "http://localhost:11434")
                model = get_config_value("ollama.model", "llama2")
                self.llm = create_ollama_llm(model_name=model, base_url=base_url)
                logger.info("Ollama LLM initialized for rule analyzer", model=model)
                return
            except Exception as e:
                logger.warning(f"Failed to initialize Ollama, trying Azure OpenAI: {e}")

        # Fallback to Azure OpenAI if Ollama not available
        try:
            self.llm = create_langchain_azure_chat_openai()
            logger.info("Azure OpenAI LLM initialized for rule analyzer")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM, will use rule-based suggestions: {e}")
            self.llm = None

    def analyze_rule_failures(
        self,
        workspace_id: str,
        unreconciled_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze rule failures for unreconciled records.

        Args:
            workspace_id: Workspace ID
            unreconciled_records: Optional list of unreconciled records.
                                 If None, fetches from recon service.

        Returns:
            Dict containing findings with failed rules and suggestions
        """
        try:
            logger.info(
                "Starting rule failure analysis",
                workspace_id=workspace_id,
                record_count=len(unreconciled_records) if unreconciled_records else 0,
            )

            findings = []

            # Step 1: Get unreconciled records if not provided
            if unreconciled_records is None:
                records_result = self.data_fetcher.fetch_records(
                    workspace_id=workspace_id
                )
                if not records_result["success"]:
                    return {
                        "success": False,
                        "error": records_result.get("error", "Failed to fetch records"),
                        "findings": [],
                    }
                unreconciled_records = records_result.get("all_records", [])

            # Step 2: Get records with both internal and MIS data
            records_with_both = []
            for record in unreconciled_records:
                # Check if record has both internal and MIS data
                # This is simplified - actual logic would check record pairs
                if self._has_both_internal_and_mis(record, workspace_id):
                    records_with_both.append(record)

            logger.info(
                "Found records with both internal and MIS data",
                count=len(records_with_both),
            )

            # Step 3: Fetch applicable rules
            rules_result = self.data_fetcher.recon_client.get_rules(workspace_id)
            if not rules_result["success"]:
                return {
                    "success": False,
                    "error": rules_result.get("error", "Failed to fetch rules"),
                    "findings": [],
                }

            rules = rules_result.get("rules", [])

            # Step 4: Evaluate rules for each record
            for record in records_with_both:
                record_id = record.get("id") or record.get("record_id")
                entity_id = record.get("rzp_entity_id") or record.get("entity_id")

                # Get internal and MIS data for this record
                internal_data, mis_data = self._get_internal_and_mis_data(
                    record, workspace_id
                )

                if not internal_data or not mis_data:
                    continue

                # Evaluate each rule
                for rule in rules:
                    rule_id = rule.get("id")
                    rule_expression = rule.get("expression") or rule.get("rule_expression")

                    if not rule_expression:
                        continue

                    # Evaluate rule (simplified - actual evaluation would use rule engine)
                    rule_passed, mismatch_details = self._evaluate_rule(
                        rule_expression, internal_data, mis_data
                    )

                    if not rule_passed:
                        # Rule failed - create finding
                        suggested_art_remarks = self._map_to_art_remarks(
                            rule, mismatch_details, internal_data, mis_data
                        )

                        findings.append({
                            "record_id": record_id,
                            "entity_id": entity_id,
                            "failed_rule_id": rule_id,
                            "failed_rule_expression": rule_expression,
                            "mismatch_details": mismatch_details,
                            "suggested_art_remarks": suggested_art_remarks,
                            "issue": "rule_matching_failure",
                            "rule": rule,
                        })

            logger.info(
                "Rule failure analysis completed",
                total_records=len(records_with_both),
                findings_count=len(findings),
            )

            return {
                "success": True,
                "findings": findings,
                "total_unreconciled": len(unreconciled_records),
                "records_with_both_data": len(records_with_both),
                "rule_failures": len(findings),
                "scenario": "C",
                "scenario_name": "rule_matching_failure",
            }

        except Exception as e:
            logger.error(
                "Failed to analyze rule failures",
                workspace_id=workspace_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "findings": [],
            }

    def _has_both_internal_and_mis(
        self, record: Dict[str, Any], workspace_id: str
    ) -> bool:
        """
        Check if record has both internal and MIS data.

        This is a simplified check. Actual implementation would
        check for record pairs or related records.

        Args:
            record: Record to check
            workspace_id: Workspace ID

        Returns:
            True if record has both internal and MIS data
        """
        # Simplified: check if record has both source types
        source_id = record.get("source_id")
        file_type_id = record.get("file_type_id")

        # TODO: Implement actual check for record pairs
        # For now, assume records with entity_id have both
        return bool(record.get("rzp_entity_id") or record.get("entity_id"))

    def _get_internal_and_mis_data(
        self, record: Dict[str, Any], workspace_id: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Get internal and MIS data for a record.

        Args:
            record: Record to get data for
            workspace_id: Workspace ID

        Returns:
            Tuple of (internal_data, mis_data)
        """
        # TODO: Implement actual data fetching for internal and MIS records
        # This would fetch related records from recon_result or record pairs
        entity_id = record.get("rzp_entity_id") or record.get("entity_id")

        # Simplified: return record data as both
        return record, record

    def _evaluate_rule(
        self,
        rule_expression: str,
        internal_data: Dict[str, Any],
        mis_data: Dict[str, Any],
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate rule expression against data.

        This is a simplified evaluation. Actual implementation would
        use a proper rule engine to evaluate JSON logic or SQL expressions.

        Args:
            rule_expression: Rule expression to evaluate
            internal_data: Internal record data
            mis_data: MIS record data

        Returns:
            Tuple of (rule_passed, mismatch_details)
        """
        # Simplified rule evaluation
        # In production, this would use a rule engine like json-logic or similar

        mismatch_details = {}

        # Simple amount matching check
        internal_amount = internal_data.get("amount")
        mis_amount = mis_data.get("amount")

        if internal_amount != mis_amount:
            mismatch_details["amount_mismatch"] = {
                "internal": internal_amount,
                "mis": mis_amount,
            }

        # Simple RRN matching check
        internal_rrn = internal_data.get("rrn") or internal_data.get("payment_id")
        mis_rrn = mis_data.get("rrn") or mis_data.get("payment_id")

        if internal_rrn != mis_rrn:
            mismatch_details["rrn_mismatch"] = {
                "internal": internal_rrn,
                "mis": mis_rrn,
            }

        # Rule passes if no mismatches found
        rule_passed = len(mismatch_details) == 0

        return rule_passed, mismatch_details

    def _map_to_art_remarks(
        self, rule: Dict[str, Any], mismatch_details: Dict[str, Any],
        internal_data: Optional[Dict[str, Any]] = None,
        mis_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Map rule failure to suggested ART remarks using AI if available.

        Args:
            rule: Failed rule
            mismatch_details: Details of what mismatched
            internal_data: Internal record data
            mis_data: MIS record data

        Returns:
            Suggested ART remarks string
        """
        # Try AI-powered generation first
        if self.llm:
            try:
                return self._generate_ai_art_remarks(
                    rule, mismatch_details, internal_data, mis_data
                )
            except Exception as e:
                logger.warning(f"AI art_remarks generation failed, using rule-based: {e}")

        # Fallback to rule-based generation
        remarks = []

        if "amount_mismatch" in mismatch_details:
            amount_info = mismatch_details["amount_mismatch"]
            remarks.append(
                f"Amount mismatch: Internal={amount_info.get('internal')}, "
                f"MIS={amount_info.get('mis')}"
            )
        if "rrn_mismatch" in mismatch_details:
            rrn_info = mismatch_details["rrn_mismatch"]
            remarks.append(
                f"RRN/Payment ID mismatch: Internal={rrn_info.get('internal')}, "
                f"MIS={rrn_info.get('mis')}"
            )

        if not remarks:
            remarks.append(
                f"Rule {rule.get('id')} failed: {rule.get('expression', 'Unknown reason')}"
            )

        return "; ".join(remarks)

    def _generate_ai_art_remarks(
        self,
        rule: Dict[str, Any],
        mismatch_details: Dict[str, Any],
        internal_data: Optional[Dict[str, Any]],
        mis_data: Optional[Dict[str, Any]],
    ) -> str:
        """
        Generate ART remarks using AI.

        Args:
            rule: Failed rule
            mismatch_details: Mismatch details
            internal_data: Internal record data
            mis_data: MIS record data

        Returns:
            AI-generated ART remarks
        """
        prompt = ART_REMARKS_GENERATION_PROMPT.format(
            rule_id=rule.get("id", "Unknown"),
            rule_expression=rule.get("expression", "Unknown"),
            mismatch_details=str(mismatch_details),
            internal_data=str(internal_data or {}),
            mis_data=str(mis_data or {}),
        )

        # Both Ollama (ChatOllama) and Azure OpenAI use the same message interface
        messages = [HumanMessage(content=prompt)]
        result = invoke_with_retry_langchain(
            self.llm,
            messages,
            operation="generate_art_remarks",
        )
        # Extract content from LangChain response
        if hasattr(result, "content"):
            return result.content.strip()
        elif isinstance(result, str):
            return result.strip()
        else:
            return str(result).strip()

