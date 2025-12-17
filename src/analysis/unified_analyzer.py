"""
Unified Analyzer - Simplified approach
1. Get workspace_id
2. Fetch all related file_types for that workspace
3. Identify unique column value from user-provided file_type
4. Query all file_types using their unique columns with that value
5. Perform analysis based on scenarios
"""

from typing import Dict, Any, List, Optional, Tuple
from src.analysis.data_fetcher import DataFetcher
from src.analysis.context_enricher import ContextEnricher
from src.analysis.rule_analyzer import RuleAnalyzer
from src.data.local_db import get_local_db
from src.utils.logging import logger
import json


class UnifiedAnalyzer:
    """
    Unified analyzer that follows a simple, straightforward approach:
    1. Get workspace_id
    2. Fetch all file_types for workspace
    3. Extract unique_column_value from user-provided file_type
    4. Query all file_types using their unique columns
    5. Analyze based on scenarios
    """

    def __init__(self):
        """Initialize unified analyzer."""
        self.data_fetcher = DataFetcher()
        self.context_enricher = ContextEnricher()
        self.rule_analyzer = RuleAnalyzer()

    def analyze(
        self,
        workspace_id: str,
        file_type_name: str,
        output_file_path: Optional[str] = None,
        unique_column_value: Optional[str] = None,
        transaction_date_range: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Main analysis method following the simplified approach.

        Args:
            workspace_id: Workspace ID
            file_type_name: File type name provided by user (MIS file type)
            output_file_path: Optional path to output file (MIS file) to extract unique_column_value
            unique_column_value: Optional unique column value (if not provided, will extract from file)
            transaction_date_range: Optional date range for filtering

        Returns:
            Dict containing analysis results for all scenarios
        """
        try:
            logger.info(
                "Starting unified analysis",
                workspace_id=workspace_id,
                file_type_name=file_type_name,
                output_file_path=output_file_path,
                unique_column_value=unique_column_value,
            )

            # Step 1: Get workspace_id (already provided)
            # Step 2: Fetch all related file_types for that workspace
            context = self.context_enricher.enrich(workspace_id=workspace_id)
            if not context:
                return {
                    "success": False,
                    "error": "Failed to fetch context for workspace",
                    "findings": [],
                }
            file_types = context.get("file_types", [])

            if not file_types:
                return {
                    "success": False,
                    "error": "No file types found for workspace",
                    "findings": [],
                }

            # Step 3: Identify unique column for the user-provided file_type
            user_file_type = None
            user_file_type_id = None
            user_unique_column = None
            
            for ft in file_types:
                if ft.get("name", "").lower() == file_type_name.lower():
                    user_file_type = ft
                    user_file_type_id = ft.get("id")
                    break

            if not user_file_type:
                return {
                    "success": False,
                    "error": f"File type '{file_type_name}' not found in workspace",
                    "findings": [],
                }

            # Get unique column for user's file_type
            db = get_local_db()
            user_unique_column = db.get_unique_column(user_file_type_id)
            if not user_unique_column:
                return {
                    "success": False,
                    "error": f"Unique column not found for file type {file_type_name}",
                    "findings": [],
                }

            # Step 3 (continued): Extract unique_column_value from output file if not provided
            if not unique_column_value and output_file_path:
                unique_column_value = self._extract_unique_column_value(
                    output_file_path, user_unique_column
                )
                if not unique_column_value:
                    return {
                        "success": False,
                        "error": f"Could not extract {user_unique_column} from output file",
                        "findings": [],
                    }

            if not unique_column_value:
                return {
                    "success": False,
                    "error": "unique_column_value is required. Either provide it directly or provide output_file_path to extract it.",
                    "findings": [],
                }

            # Step 4: Use unique_column_value to query data across all file_types
            # Store results in a dict mapping file_type_id to records
            file_type_records = {}
            internal_file_type_ids = []
            mis_file_type_ids = []

            for ft in file_types:
                ft_id = ft.get("id")
                source_category = ft.get("source_category", "").lower()

                # Classify as Internal or MIS
                is_internal = "internal" in source_category
                is_mis = "bank" in source_category or "mis" in source_category

                if is_internal:
                    internal_file_type_ids.append(ft_id)
                elif is_mis:
                    mis_file_type_ids.append(ft_id)

                # Get unique column for this file_type
                unique_col = db.get_unique_column(ft_id)
                if unique_col:
                    # Query journal using unique_column_value
                    journal_result = self.data_fetcher.fetch_journal_records(
                        file_type_id=ft_id,
                        unique_column_value=unique_column_value,
                        recon_status=None,  # Get all records regardless of status
                    )

                    if journal_result and journal_result.get("success"):
                        records = journal_result.get("records", [])
                        if records:  # Only store if records found
                            file_type_records[ft_id] = records
                            logger.debug(
                                "Fetched records for file type",
                                file_type_id=ft_id,
                                record_count=len(records),
                            )

            # Step 5: Perform analysis based on scenarios
            findings = []
            all_scenarios = []

            # Step 5: Perform analysis based on scenarios
            # Check which scenarios apply based on what records we found

            # Scenario A: If recon status is reconciled, check transaction table
            # Check all records to see if any are reconciled
            has_reconciled = False
            for ft_id, records in file_type_records.items():
                for record in records:
                    if record.get("recon_status") == "Reconciled":
                        has_reconciled = True
                        break
                if has_reconciled:
                    break

            if has_reconciled:
                scenario_a_findings = self._analyze_scenario_a(
                    workspace_id, file_type_records, unique_column_value, transaction_date_range
                )
                if scenario_a_findings:
                    findings.extend(scenario_a_findings)
                    all_scenarios.append("A")

            # Scenario B: If data exists only in MIS and not in Internal, check payments
            has_mis = any(ft_id in mis_file_type_ids and file_type_records.get(ft_id) for ft_id in mis_file_type_ids)
            has_internal = any(ft_id in internal_file_type_ids and file_type_records.get(ft_id) for ft_id in internal_file_type_ids)

            if has_mis and not has_internal:
                scenario_b_findings = self._analyze_scenario_b(
                    workspace_id,
                    file_type_records,
                    mis_file_type_ids,
                    internal_file_type_ids,
                    unique_column_value,
                    transaction_date_range,
                )
                if scenario_b_findings:
                    findings.extend(scenario_b_findings)
                    all_scenarios.append("B")

            # Scenario C: If records present in both but unreconciled, apply rules
            if has_mis and has_internal:
                scenario_c_findings = self._analyze_scenario_c(
                    workspace_id,
                    file_type_records,
                    mis_file_type_ids,
                    internal_file_type_ids,
                    unique_column_value,
                )
                if scenario_c_findings:
                    findings.extend(scenario_c_findings)
                    all_scenarios.append("C")

            return {
                "success": True,
                "findings": findings,
                "scenarios_detected": all_scenarios,
                "file_type_records": {
                    ft_id: len(records) for ft_id, records in file_type_records.items()
                },
                "unique_column_value": unique_column_value,
            }

        except Exception as e:
            logger.error(
                "Failed unified analysis",
                workspace_id=workspace_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "findings": [],
            }

    def _extract_unique_column_value(
        self, file_path: str, unique_column: str
    ) -> Optional[str]:
        """
        Extract unique column value from output file.

        Args:
            file_path: Path to output file (CSV/Excel)
            unique_column: Name of unique column to extract

        Returns:
            Unique column value or None
        """
        try:
            import pandas as pd
            import os

            if not os.path.exists(file_path):
                logger.error("Output file not found", file_path=file_path)
                return None

            # Read file based on extension
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            else:
                logger.error("Unsupported file format", file_path=file_path)
                return None

            # Extract unique column value (take first row)
            if unique_column in df.columns:
                value = df[unique_column].iloc[0] if len(df) > 0 else None
                logger.info(
                    "Extracted unique column value",
                    unique_column=unique_column,
                    value=value,
                )
                return str(value) if value is not None else None
            else:
                logger.error(
                    "Unique column not found in file",
                    unique_column=unique_column,
                    available_columns=list(df.columns),
                )
                return None

        except Exception as e:
            logger.error(
                "Failed to extract unique column value",
                file_path=file_path,
                unique_column=unique_column,
                error=str(e),
            )
            return None

    def _analyze_scenario_a(
        self,
        workspace_id: str,
        file_type_records: Dict[str, List[Dict[str, Any]]],
        unique_column_value: str,
        transaction_date_range: Optional[Tuple[str, str]],
    ) -> List[Dict[str, Any]]:
        """
        Scenario A: If recon status is reconciled, check transaction table.
        """
        findings = []

        # Check all records across all file_types
        for ft_id, records in file_type_records.items():
            for record in records:
                recon_status = record.get("recon_status")
                if recon_status == "Reconciled":
                    # Check if reconciled_at is NULL in transactions table
                    entity_id = record.get("entity_id")
                    if entity_id:
                        db = get_local_db()
                        transaction = db.query_transactions(entity_id)
                        # If transaction exists but reconciled_at is NULL, or if transaction doesn't exist at all
                        if transaction:
                            reconciled_at = transaction[0].get("reconciled_at")
                            if not reconciled_at:
                                findings.append({
                                    "scenario": "A",
                                    "entity_id": entity_id,
                                    "file_type_id": ft_id,
                                    "issue": "recon_at_not_updated",
                                    "recon_status": recon_status,
                                    "recon_at_in_journal": record.get("recon_at"),
                                    "suggestion": "Update transactions table with reconciled_at timestamp",
                                })
                        else:
                            # Transaction record doesn't exist - this is also an issue
                            findings.append({
                                "scenario": "A",
                                "entity_id": entity_id,
                                "file_type_id": ft_id,
                                "issue": "transaction_record_missing",
                                "recon_status": recon_status,
                                "recon_at_in_journal": record.get("recon_at"),
                                "suggestion": "Transaction record missing in transactions table. Create transaction record with reconciled_at timestamp.",
                            })

        return findings

    def _analyze_scenario_b(
        self,
        workspace_id: str,
        file_type_records: Dict[str, List[Dict[str, Any]]],
        mis_file_type_ids: List[str],
        internal_file_type_ids: List[str],
        unique_column_value: str,
        transaction_date_range: Optional[Tuple[str, str]],
    ) -> List[Dict[str, Any]]:
        """
        Scenario B: If data exists only in MIS and not in Internal, check payments.
        """
        findings = []

        # Check if we have MIS records but no Internal records
        has_mis = any(ft_id in mis_file_type_ids and file_type_records.get(ft_id) for ft_id in mis_file_type_ids)
        has_internal = any(ft_id in internal_file_type_ids and file_type_records.get(ft_id) for ft_id in internal_file_type_ids)

        if has_mis and not has_internal:
            # Get MIS record
            mis_record = None
            for ft_id in mis_file_type_ids:
                records = file_type_records.get(ft_id, [])
                if records:
                    mis_record = records[0]
                    break

            if mis_record:
                # Check payments table
                db = get_local_db()
                payment = db.query_payments(unique_column_value)

                if not payment:
                    findings.append({
                        "scenario": "B",
                        "entity_id": unique_column_value,
                        "issue": "payment_not_found",
                        "payment_exists": False,
                        "data_lag_detected": False,
                        "suggestion": f"Payment {unique_column_value} not found in payments table. This indicates the payment may not exist in the system.",
                    })
                else:
                    # Check for data lag
                    payment_info = payment[0]
                    updated_at = payment_info.get("updated_at")
                    datalake_updated_at = payment_info.get("_datalake_updated_at")

                    if updated_at is not None and datalake_updated_at is not None:
                        try:
                            lag_seconds = abs(updated_at - datalake_updated_at)
                            if lag_seconds and lag_seconds > 3600:  # > 1 hour
                                findings.append({
                                    "scenario": "B",
                                    "entity_id": unique_column_value,
                                    "issue": "data_lag_detected",
                                    "payment_exists": True,
                                    "data_lag_detected": True,
                                    "lag_seconds": lag_seconds,
                                    "suggestion": f"Payment {unique_column_value} exists but data lag detected. Time difference: {lag_seconds/3600:.2f} hours. Consider re-ingesting internal file.",
                                })
                            else:
                                findings.append({
                                    "scenario": "B",
                                    "entity_id": unique_column_value,
                                    "issue": "internal_data_missing",
                                    "payment_exists": True,
                                    "data_lag_detected": False,
                                    "suggestion": f"Payment {unique_column_value} exists in payments table. Internal data should be present but is missing. Re-ingest internal file.",
                                })
                        except (TypeError, ValueError) as e:
                            logger.warning(
                                "Could not calculate lag",
                                error=str(e),
                                updated_at=updated_at,
                                datalake_updated_at=datalake_updated_at,
                            )
                            findings.append({
                                "scenario": "B",
                                "entity_id": unique_column_value,
                                "issue": "internal_data_missing",
                                "payment_exists": True,
                                "data_lag_detected": False,
                                "suggestion": f"Payment {unique_column_value} exists in payments table. Internal data should be present but is missing. Re-ingest internal file.",
                            })

        return findings

    def _analyze_scenario_c(
        self,
        workspace_id: str,
        file_type_records: Dict[str, List[Dict[str, Any]]],
        mis_file_type_ids: List[str],
        internal_file_type_ids: List[str],
        unique_column_value: str,
    ) -> List[Dict[str, Any]]:
        """
        Scenario C: If records present in both but unreconciled, apply matching rules.
        """
        findings = []

        # Check if we have both MIS and Internal records
        mis_records = []
        internal_records = []

        for ft_id in mis_file_type_ids:
            records = file_type_records.get(ft_id, [])
            mis_records.extend(records)

        for ft_id in internal_file_type_ids:
            records = file_type_records.get(ft_id, [])
            internal_records.extend(records)

        if mis_records and internal_records:
            # Check if any are unreconciled
            unreconciled_mis = [r for r in mis_records if r.get("recon_status") == "Unreconciled"]
            unreconciled_internal = [r for r in internal_records if r.get("recon_status") == "Unreconciled"]

            if unreconciled_mis or unreconciled_internal:
                # Use rule analyzer to check rule failures
                # Create a combined record for analysis
                combined_record = unreconciled_mis[0] if unreconciled_mis else mis_records[0]
                
                # Check if rules are failing
                has_both, internal_data, mis_data = self.rule_analyzer._has_both_internal_and_mis(
                    combined_record, workspace_id
                )

                if has_both and internal_data and mis_data:
                    # Evaluate rules
                    context = self.context_enricher.enrich(workspace_id=workspace_id)
                    resolved_rules = context.get("resolved_rules", [])

                    # Get file type IDs
                    file_type1_id = internal_data.get("file_type_id")
                    file_type2_id = mis_data.get("file_type_id")

                    # Get applicable rules
                    applicable_rules = self.context_enricher.get_resolved_rules_for_file_types(
                        context, file_type1_id, file_type2_id
                    )

                    if not applicable_rules:
                        applicable_rules = resolved_rules

                    # Evaluate each rule
                    for rule_recon_state_map in applicable_rules:
                        resolved_expression = rule_recon_state_map.get("resolved_expression", "")
                        if not resolved_expression:
                            continue

                        rule_passed, mismatch_details = self.rule_analyzer._evaluate_rule(
                            resolved_expression, internal_data, mis_data
                        )

                        if not rule_passed:
                            suggested_art_remarks = self.rule_analyzer._map_to_art_remarks(
                                {"id": rule_recon_state_map.get("id"), "rule": resolved_expression},
                                mismatch_details,
                                internal_data,
                                mis_data,
                                rule_recon_state_map
                            )

                            findings.append({
                                "scenario": "C",
                                "entity_id": unique_column_value,
                                "issue": "rule_matching_failure",
                                "failed_rule_id": rule_recon_state_map.get("id"),
                                "failed_rule_expression": resolved_expression,
                                "mismatch_details": mismatch_details,
                                "suggested_art_remarks": suggested_art_remarks,
                            })
                            break  # Only report first failing rule

        return findings

