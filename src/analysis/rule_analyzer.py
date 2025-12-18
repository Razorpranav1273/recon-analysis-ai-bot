"""
Rule Analyzer (Scenario C)
Analyzes rule matching failures for unreconciled records.
Uses AI to generate intelligent art_remarks suggestions.
"""

from typing import Dict, Any, List, Optional, Tuple
from src.analysis.data_fetcher import DataFetcher
from src.analysis.context_enricher import ContextEnricher
from src.utils.logging import logger
from src.utils.llm_utils import (
    create_langchain_azure_chat_openai,
    create_ollama_llm,
    invoke_with_retry_langchain,
)
from src.utils.config_reader import get_config_value
from src.analysis.prompts import (
    ART_REMARKS_GENERATION_PROMPT,
    RULE_FAILURE_ANALYSIS_PROMPT,
    RULE_ANALYSIS_FEW_SHOT_EXAMPLES,
)
import json
import re
from datetime import datetime
from langchain_core.messages import HumanMessage


class RuleAnalyzer:
    """
    Analyzer for Scenario C: Rule matching failures.
    Uses AI to generate intelligent art_remarks suggestions.
    """

    def __init__(self):
        """Initialize rule analyzer."""
        self.data_fetcher = DataFetcher()
        self.context_enricher = ContextEnricher()
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

            # Step 1: Get unreconciled records from journal tables if not provided
            if unreconciled_records is None:
                records_result = self.data_fetcher.fetch_records(
                    workspace_id=workspace_id,
                    recon_status="Unreconciled",  # Fetch unreconciled records from journal
                )
                if not records_result["success"]:
                    return {
                        "success": False,
                        "error": records_result.get("error", "Failed to fetch records from journal"),
                        "findings": [],
                    }
                unreconciled_records = records_result.get("all_records", [])

            # Step 2: Get records with both internal and MIS data
            records_with_both = []
            for record in unreconciled_records:
                # Check if record has both internal and MIS data by querying journal
                has_both, internal_data, mis_data = self._has_both_internal_and_mis(record, workspace_id)
                if has_both:
                    # Store both data in record for later use
                    record["_internal_data"] = internal_data
                    record["_mis_data"] = mis_data
                    records_with_both.append(record)

            logger.info(
                "Found records with both internal and MIS data",
                count=len(records_with_both),
            )

            # Step 3: Enrich context (workspace, file types, rules, rule_recon_state_map)
            context = self.context_enricher.enrich(workspace_id=workspace_id)
            
            # Extract rules and resolved rules from context
            rules_dict = context.get("rules", {})
            rules = list(rules_dict.values())  # Convert dict to list for compatibility
            resolved_rules = context.get("resolved_rules", [])
            
            if not rules and not resolved_rules:
                logger.warning("No rules found in context", workspace_id=workspace_id)

            # Step 4: Evaluate rules for each record
            # Get unique_column for the workspace file_types (we'll use it for entity extraction)
            from src.data.local_db import get_local_db
            local_db = get_local_db()
            
            for record in records_with_both:
                record_id = record.get("id") or record.get("record_id")
                
                # Extract entity_id using unique_column from file_type metadata
                file_type_id = record.get("file_type_id")
                entity_id = None
                
                if file_type_id:
                    unique_col = local_db.get_unique_column(file_type_id)
                    if unique_col:
                        record_data = record.get("record_data", {})
                        if isinstance(record_data, dict):
                            entity_id = record_data.get(unique_col)
                
                # Fallback: try common entity_id field names (only if unique_column not available)
                if not entity_id:
                    record_data = record.get("record_data", {})
                    if isinstance(record_data, dict):
                        # Try standard entity_id fields as fallback
                        entity_id = (
                            record_data.get("entity_id") or
                            record_data.get("rzp_entity_id")
                        )
                    if not entity_id:
                        entity_id = record.get("entity_id") or record.get("rzp_entity_id")

                # Get internal and MIS data for this record
                internal_data, mis_data = self._get_internal_and_mis_data(
                    record, workspace_id
                )

                if not internal_data or not mis_data:
                    continue

                # Get file type IDs for this record pair
                file_type1_id = internal_data.get("file_type_id") or internal_data.get("source_id")
                file_type2_id = mis_data.get("file_type_id") or mis_data.get("source_id")

                # Get applicable resolved rules for this file type pair
                applicable_rules = self.context_enricher.get_resolved_rules_for_file_types(
                    context, file_type1_id, file_type2_id
                )

                # If no applicable rules, fall back to all resolved rules
                if not applicable_rules:
                    applicable_rules = resolved_rules

                # Evaluate each applicable rule
                for rule_recon_state_map in applicable_rules:
                    resolved_expression = rule_recon_state_map.get("resolved_expression", "")
                    if not resolved_expression:
                        continue

                    # Evaluate rule (simplified - actual evaluation would use rule engine)
                    rule_passed, mismatch_details = self._evaluate_rule(
                        resolved_expression, internal_data, mis_data
                    )

                    if not rule_passed:
                        # Rule failed - create finding with full context
                        suggested_art_remarks = self._map_to_art_remarks(
                            {"id": rule_recon_state_map.get("id"), "rule": resolved_expression},
                            mismatch_details,
                            internal_data,
                            mis_data,
                            rule_recon_state_map
                        )

                        findings.append({
                            "record_id": record_id,
                            "entity_id": entity_id,
                            "failed_rule_id": rule_recon_state_map.get("id"),
                            "failed_rule_expression": resolved_expression,
                            "rule_recon_state_map_id": rule_recon_state_map.get("id"),
                            "expected_state": rule_recon_state_map.get("recon_state"),
                            "expected_art_remarks": rule_recon_state_map.get("art_remarks"),
                            "seq_number": rule_recon_state_map.get("seq_number"),
                            "mismatch_details": mismatch_details,
                            "suggested_art_remarks": suggested_art_remarks,
                            "issue": "rule_matching_failure",
                            "rule_recon_state_map": rule_recon_state_map,
                        })
                        
                        # Only process first failing rule (highest priority)
                        break

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
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Check if record has both internal and MIS data by querying journal.

        Args:
            record: Record to check
            workspace_id: Workspace ID

        Returns:
            Tuple of (has_both, internal_data, mis_data)
        """
        # Get internal and MIS data
        internal_data, mis_data = self._get_internal_and_mis_data(record, workspace_id)
        has_both = internal_data is not None and mis_data is not None
        return has_both, internal_data, mis_data

    def _get_internal_and_mis_data(
        self, record: Dict[str, Any], workspace_id: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Get internal and MIS data for a record from journal/Hudi tables.

        Args:
            record: Record to get data for
            workspace_id: Workspace ID

        Returns:
            Tuple of (internal_data, mis_data)
        """
        # Extract entity_id using unique_column from file_type metadata
        # Note: data_fetcher merges record_data into top-level, so check top-level first
        file_type_id = record.get("file_type_id")
        entity_id = None
        
        if file_type_id:
            from src.data.local_db import get_local_db
            local_db = get_local_db()
            unique_col = local_db.get_unique_column(file_type_id)
            if unique_col:
                # Check top-level first (data_fetcher merges record_data)
                entity_id = record.get(unique_col)
                # If not found, check record_data field
                if not entity_id:
                    record_data = record.get("record_data", {})
                    if isinstance(record_data, str):
                        try:
                            record_data = json.loads(record_data)
                        except:
                            record_data = {}
                    if isinstance(record_data, dict):
                        entity_id = record_data.get(unique_col)
        
        # Fallback: try common entity_id field names (only if unique_column not available)
        if not entity_id:
            # Check top-level first (data_fetcher merges record_data)
            entity_id = (
                record.get("entity_id") or
                record.get("extracted_payment_id") or
                record.get("pay_id") or
                record.get("rzp_entity_id")
            )
            # If not found, check record_data field
            if not entity_id:
                record_data = record.get("record_data", {})
                if isinstance(record_data, str):
                    try:
                        record_data = json.loads(record_data)
                    except:
                        record_data = {}
                if isinstance(record_data, dict):
                    entity_id = (
                        record_data.get("entity_id") or
                        record_data.get("extracted_payment_id") or
                        record_data.get("pay_id") or
                        record_data.get("rzp_entity_id")
                    )
        
        if not entity_id:
            return None, None

        # Get file types to identify internal vs MIS
        context = self.context_enricher.enrich(workspace_id=workspace_id)
        file_types = context.get("file_types", [])
        
        # Get the file_type_id of the current record
        record_file_type_id = record.get("file_type_id")
        
        internal_file_type_id = None
        mis_file_type_id = None
        
        # Use source_category for classification (same as gap_analyzer)
        # We need to find both Internal and MIS file types, regardless of which one the record is
        for ft in file_types:
            source_category = ft.get("source_category", "").lower()
            file_type_id = ft.get("id")
            
            if "internal" in source_category:
                # Store first Internal file type found, or prefer the one matching the record
                if internal_file_type_id is None or file_type_id == record_file_type_id:
                    internal_file_type_id = file_type_id
            elif "bank" in source_category or "mis" in source_category:
                # Store first MIS file type found, or prefer the one matching the record
                if mis_file_type_id is None or file_type_id == record_file_type_id:
                    mis_file_type_id = file_type_id
            else:
                # Fallback to name-based classification
                file_type_name = ft.get("name", "").lower()
                if "rzp" in file_type_name and "payment_report" in file_type_name:
                    if internal_file_type_id is None or file_type_id == record_file_type_id:
                        internal_file_type_id = file_type_id
                elif "bank" in file_type_name or "mis" in file_type_name:
                    if mis_file_type_id is None or file_type_id == record_file_type_id:
                        mis_file_type_id = file_type_id

        internal_data = None
        mis_data = None

        # Fetch internal record from journal using unique_column
        if internal_file_type_id:
            # Get unique_column for internal file_type
            from src.data.local_db import get_local_db
            local_db = get_local_db()
            internal_unique_col = local_db.get_unique_column(internal_file_type_id)
            
            if internal_unique_col:
                # Use unique_column_value for filtering
                # Don't filter by recon_status - we want to find matching records regardless of status
                journal_result = self.data_fetcher.fetch_journal_records(
                    file_type_id=internal_file_type_id,
                    unique_column_value=entity_id,
                    recon_status=None,  # Don't filter by status
                )
            else:
                # Fallback to entity_ids
                journal_result = self.data_fetcher.fetch_journal_records(
                    file_type_id=internal_file_type_id,
                    entity_ids=[entity_id],
                    recon_status=None,  # Don't filter by status
                )
            
            if journal_result.get("success") and journal_result.get("records"):
                internal_record = journal_result["records"][0]
                # data_fetcher merges record_data into top-level, so use the record directly
                internal_data = internal_record

        # Fetch MIS record from journal using unique_column
        if mis_file_type_id:
            # Get unique_column for MIS file_type
            from src.data.local_db import get_local_db
            local_db = get_local_db()
            mis_unique_col = local_db.get_unique_column(mis_file_type_id)
            
            if mis_unique_col:
                # Use unique_column_value for filtering
                # Don't filter by recon_status - we want to find matching records regardless of status
                journal_result = self.data_fetcher.fetch_journal_records(
                    file_type_id=mis_file_type_id,
                    unique_column_value=entity_id,
                    recon_status=None,  # Don't filter by status
                )
            else:
                # Fallback to entity_ids
                journal_result = self.data_fetcher.fetch_journal_records(
                    file_type_id=mis_file_type_id,
                    entity_ids=[entity_id],
                    recon_status=None,  # Don't filter by status
                )
            
            if journal_result.get("success") and journal_result.get("records"):
                mis_record = journal_result["records"][0]
                # data_fetcher merges record_data into top-level, so use the record directly
                mis_data = mis_record

        return internal_data, mis_data

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
        internal_amount = internal_data.get("amount") or internal_data.get("abs_amount")
        mis_amount = mis_data.get("amount") or mis_data.get("abs_amount")

        # Only compare if both are not None
        if internal_amount is not None and mis_amount is not None and internal_amount != mis_amount:
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
        rule_recon_state_map: Optional[Dict[str, Any]] = None,
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
                    rule, mismatch_details, internal_data, mis_data, rule_recon_state_map
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
        rule_recon_state_map: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate ART remarks using AI with enhanced prompts.

        Args:
            rule: Failed rule
            mismatch_details: Mismatch details
            internal_data: Internal record data
            mis_data: MIS record data
            rule_recon_state_map: Optional rule_recon_state_map entry with expected state/remarks

        Returns:
            AI-generated ART remarks
        """
        # Use enhanced prompt with rule_recon_state_map context if available
        if rule_recon_state_map:
            prompt = RULE_FAILURE_ANALYSIS_PROMPT.format(
                rule_id=rule.get("id", "Unknown"),
                rule_expression=rule.get("expression", rule.get("rule", "Unknown")),
                expected_state=rule_recon_state_map.get("recon_state", "Unknown"),
                expected_art_remarks=rule_recon_state_map.get("art_remarks", ""),
                seq_number=rule_recon_state_map.get("seq_number", 0),
                internal_data=self._format_data_for_prompt(internal_data),
                mis_data=self._format_data_for_prompt(mis_data),
            )
        else:
            # Fallback to simpler prompt
            prompt = ART_REMARKS_GENERATION_PROMPT.format(
                rule_id=rule.get("id", "Unknown"),
                rule_expression=rule.get("expression", rule.get("rule", "Unknown")),
                mismatch_details=self._format_data_for_prompt(mismatch_details),
                internal_data=self._format_data_for_prompt(internal_data),
                mis_data=self._format_data_for_prompt(mis_data),
            )

        # Both Ollama (ChatOllama) and Azure OpenAI use the same message interface
        messages = [HumanMessage(content=prompt)]
        result = invoke_with_retry_langchain(
            self.llm,
            messages,
            operation="generate_art_remarks",
        )
        
        # Extract content from LangChain response
        content = ""
        if hasattr(result, "content"):
            content = result.content.strip()
        elif isinstance(result, str):
            content = result.strip()
        else:
            content = str(result).strip()
        
        # Try to extract JSON if using structured prompt
        if rule_recon_state_map:
            json_data = self._extract_json_from_response(content)
            if json_data and "recommendations" in json_data:
                return json_data["recommendations"].get("suggested_art_remarks", content)
        
        # Extract just the remark if prompt included examples
        # Look for "ART Remark:" or similar markers
        if "ART Remark:" in content:
            content = content.split("ART Remark:")[-1].strip()
        elif "art_remarks" in content.lower():
            # Try to extract from JSON-like structure
            json_match = re.search(r'"suggested_art_remarks"\s*:\s*"([^"]+)"', content)
            if json_match:
                return json_match.group(1)
        
        return content
    
    def _extract_json_from_response(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from AI response, handling cases where response includes text + JSON.
        
        Args:
            content: Raw AI response content
            
        Returns:
            Parsed JSON dict or None if extraction fails
        """
        # Try to find JSON block in response
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Try parsing entire content as JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _format_data_for_prompt(self, data: Dict[str, Any]) -> str:
        """
        Format data dictionary for prompt inclusion, handling special cases.
        
        Args:
            data: Data dictionary to format
            
        Returns:
            Formatted string representation
        """
        if not data:
            return "{}"
        
        # Create a clean copy for formatting
        formatted = {}
        for key, value in data.items():
            # Handle None values
            if value is None:
                formatted[key] = "null"
            # Handle datetime objects
            elif isinstance(value, datetime):
                formatted[key] = value.isoformat()
            # Handle numeric values (preserve as-is)
            elif isinstance(value, (int, float)):
                formatted[key] = value
            # Handle strings
            elif isinstance(value, str):
                formatted[key] = value
            # Handle nested dicts/lists
            else:
                formatted[key] = value
        
        return json.dumps(formatted, indent=2, default=str)
