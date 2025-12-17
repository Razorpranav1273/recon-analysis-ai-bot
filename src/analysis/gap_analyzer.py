"""
Gap Analyzer (Scenario B)
Analyzes missing internal data scenarios.
"""

from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from src.analysis.data_fetcher import DataFetcher
from src.utils.logging import logger


class GapAnalyzer:
    """
    Analyzer for Scenario B: Missing internal data.
    """

    def __init__(self):
        """Initialize gap analyzer."""
        self.data_fetcher = DataFetcher()

    def analyze_missing_internal_data(
        self,
        workspace_id: str,
        transaction_date_range: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze missing internal data.

        Args:
            workspace_id: Workspace ID
            transaction_date_range: Optional tuple of (start_date, end_date)

        Returns:
            Dict containing findings with MIS records missing internal data
        """
        try:
            logger.info(
                "Starting missing internal data analysis",
                workspace_id=workspace_id,
                date_range=transaction_date_range,
            )

            findings = []

            # Step 1: Fetch all records
            records_result = self.data_fetcher.fetch_records(
                workspace_id=workspace_id,
                transaction_date_range=transaction_date_range,
            )

            if not records_result["success"]:
                return {
                    "success": False,
                    "error": records_result.get("error", "Failed to fetch records"),
                    "findings": [],
                }

            mis_records = records_result.get("mis_records", [])
            internal_records = records_result.get("internal_records", [])

            logger.info(
                "Fetched records for gap analysis",
                mis_count=len(mis_records),
                internal_count=len(internal_records),
            )

            # Step 2: Compare MIS records with internal records
            # Group internal records by transaction date and amount for matching
            internal_by_date = {}
            for internal in internal_records:
                txn_date = internal.get("transaction_date")
                amount = internal.get("amount")
                if txn_date:
                    if txn_date not in internal_by_date:
                        internal_by_date[txn_date] = []
                    internal_by_date[txn_date].append(internal)

            # Step 3: Find MIS records with no matching internal record
            for mis_record in mis_records:
                txn_date = mis_record.get("transaction_date")
                mis_amount = mis_record.get("amount")
                mis_id = mis_record.get("id") or mis_record.get("record_id")

                # Try to find matching internal record
                matching_internal = None
                if txn_date in internal_by_date:
                    for internal in internal_by_date[txn_date]:
                        # Match by date and optionally by amount
                        if mis_amount and internal.get("amount") == mis_amount:
                            matching_internal = internal
                            break
                        # If no amount match, use first record for same date
                        if not matching_internal:
                            matching_internal = internal

                if not matching_internal:
                    # MIS record has no matching internal record
                    # Check if internal file ingestion exists (simplified check)
                    internal_file_exists = self._check_internal_file_ingestion(
                        workspace_id, txn_date
                    )

                    suggestion = (
                        f"Re-ingest internal file for date: {txn_date}"
                        if internal_file_exists
                        else f"Internal file not ingested for date: {txn_date}"
                    )

                    findings.append({
                        "mis_record_id": mis_id,
                        "transaction_date": txn_date,
                        "amount": mis_amount,
                        "issue": "internal_data_missing",
                        "suggestion": suggestion,
                        "internal_file_ingested": internal_file_exists,
                        "mis_record": mis_record,
                    })

            logger.info(
                "Missing internal data analysis completed",
                total_mis=len(mis_records),
                findings_count=len(findings),
            )

            return {
                "success": True,
                "findings": findings,
                "total_mis_records": len(mis_records),
                "total_internal_records": len(internal_records),
                "missing_internal": len(findings),
                "scenario": "B",
                "scenario_name": "internal_data_missing",
            }

        except Exception as e:
            logger.error(
                "Failed to analyze missing internal data",
                workspace_id=workspace_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "findings": [],
            }

    def _check_internal_file_ingestion(
        self, workspace_id: str, transaction_date: str
    ) -> bool:
        """
        Check if internal file was ingested for given date.

        Args:
            workspace_id: Workspace ID
            transaction_date: Transaction date to check (YYYY-MM-DD)

        Returns:
            True if internal file ingestion exists, False otherwise
        """
        try:
            result = self.data_fetcher.recon_client.check_file_ingestion(
                workspace_id=workspace_id,
                transaction_date=transaction_date,
                file_type_name="internal",
            )

            if result["success"]:
                file_ingested = result.get("file_ingested", False)
                logger.debug(
                    "File ingestion check completed",
                    workspace_id=workspace_id,
                    transaction_date=transaction_date,
                    file_ingested=file_ingested,
                    file_count=result.get("file_count", 0),
                )
                return file_ingested

            logger.warning(
                "Failed to check file ingestion",
                workspace_id=workspace_id,
                transaction_date=transaction_date,
                error=result.get("error"),
            )
            return False

        except Exception as e:
            logger.error(
                "Exception checking file ingestion",
                workspace_id=workspace_id,
                transaction_date=transaction_date,
                error=str(e),
            )
            return False

    def analyze_from_report(
        self, records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze records from a parsed report (CSV/Excel) for missing internal data.
        No API calls needed - works directly on the report data.

        Args:
            records: List of records from parsed report

        Returns:
            Dict containing findings
        """
        try:
            logger.info(
                "Starting gap analysis from report",
                record_count=len(records),
            )

            findings = []
            mis_count = 0
            internal_count = 0

            # First pass: categorize records as internal or MIS
            internal_records = []
            mis_records = []

            for record in records:
                # Determine if record is internal or MIS based on common column patterns
                source_type = (
                    record.get("source_type") or 
                    record.get("Source Type") or 
                    record.get("file_type") or
                    record.get("type") or
                    ""
                ).lower()
                
                is_internal = record.get("is_internal", False)
                
                # Check various indicators for internal vs MIS
                if is_internal or "internal" in source_type or "rzp" in source_type or "razorpay" in source_type:
                    internal_records.append(record)
                    internal_count += 1
                elif "mis" in source_type or "bank" in source_type or "external" in source_type:
                    mis_records.append(record)
                    mis_count += 1
                else:
                    # Default: check for common column patterns
                    # If record has 'bank_rrn' or 'bank_amount', likely MIS
                    if record.get("bank_rrn") or record.get("Bank RRN"):
                        mis_records.append(record)
                        mis_count += 1
                    else:
                        internal_records.append(record)
                        internal_count += 1

            # Second pass: find MIS records without matching internal records
            # Group internal records by date and amount for matching
            internal_by_date = {}
            for internal in internal_records:
                txn_date = (
                    internal.get("transaction_date") or 
                    internal.get("Transaction Date") or
                    internal.get("txn_date") or
                    internal.get("date")
                )
                if txn_date:
                    if txn_date not in internal_by_date:
                        internal_by_date[txn_date] = []
                    internal_by_date[txn_date].append(internal)

            # Find MIS records with no matching internal
            for mis_record in mis_records:
                txn_date = (
                    mis_record.get("transaction_date") or 
                    mis_record.get("Transaction Date") or
                    mis_record.get("txn_date") or
                    mis_record.get("date")
                )
                mis_amount = (
                    mis_record.get("amount") or 
                    mis_record.get("Amount") or
                    mis_record.get("bank_amount")
                )
                mis_id = (
                    mis_record.get("id") or 
                    mis_record.get("record_id") or
                    mis_record.get("Record ID")
                )

                # Try to find matching internal record
                matching_internal = None
                if txn_date in internal_by_date:
                    for internal in internal_by_date[txn_date]:
                        internal_amount = (
                            internal.get("amount") or 
                            internal.get("Amount")
                        )
                        # Match by date and amount
                        if mis_amount and internal_amount and str(mis_amount) == str(internal_amount):
                            matching_internal = internal
                            break

                if not matching_internal:
                    findings.append({
                        "mis_record_id": mis_id,
                        "transaction_date": txn_date,
                        "amount": mis_amount,
                        "issue": "internal_data_missing",
                        "suggestion": f"Internal data missing for transaction date: {txn_date}",
                        "mis_record": mis_record,
                    })

            logger.info(
                "Gap analysis from report completed",
                total_records=len(records),
                internal_count=internal_count,
                mis_count=mis_count,
                findings_count=len(findings),
            )

            return {
                "success": True,
                "findings": findings,
                "total_records": len(records),
                "total_mis_records": mis_count,
                "total_internal_records": internal_count,
                "missing_internal": len(findings),
                "scenario": "B",
                "scenario_name": "internal_data_missing",
            }

        except Exception as e:
            logger.error(
                "Failed to analyze gaps from report",
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "findings": [],
            }

