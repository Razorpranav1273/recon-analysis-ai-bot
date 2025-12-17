"""
Recon Status Analyzer (Scenario A)
Analyzes records where recon_at is not updated in txn_entity.
"""

from typing import Dict, Any, List, Tuple, Optional
from src.analysis.data_fetcher import DataFetcher
from src.utils.logging import logger


class ReconStatusAnalyzer:
    """
    Analyzer for Scenario A: recon_at not updated in txn_entity.
    """

    def __init__(self):
        """Initialize recon status analyzer."""
        self.data_fetcher = DataFetcher()

    def analyze_recon_at_missing(
        self,
        workspace_id: str,
        transaction_date_range: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze records where recon_at is missing in txn_entity.

        Args:
            workspace_id: Workspace ID
            transaction_date_range: Optional tuple of (start_date, end_date)

        Returns:
            Dict containing findings with record IDs, entity IDs, and suggestions
        """
        try:
            logger.info(
                "Starting recon_at missing analysis",
                workspace_id=workspace_id,
                date_range=transaction_date_range,
            )

            findings = []

            # Step 1: Fetch records with recon_status = 'Reconciled'
            recon_results = self.data_fetcher.recon_client.get_recon_results(
                workspace_id=workspace_id
            )

            if not recon_results["success"]:
                return {
                    "success": False,
                    "error": recon_results.get("error", "Failed to fetch recon results"),
                    "findings": [],
                }

            # Filter for reconciled records with recon_at timestamp
            reconciled_records = []
            for result in recon_results.get("results", []):
                if result.get("recon_status") == "Reconciled":
                    recon_at = result.get("recon_at")
                    if recon_at:  # Has recon_at in recon_result
                        record_id = result.get("record_id")
                        entity_id = result.get("rzp_entity_id") or result.get("entity_id")
                        if record_id and entity_id:
                            reconciled_records.append({
                                "record_id": record_id,
                                "entity_id": entity_id,
                                "recon_at": recon_at,
                                "recon_result": result,
                            })

            logger.info(
                "Found reconciled records with recon_at",
                count=len(reconciled_records),
            )

            # Step 2: Check txn_entity table for missing recon_at
            if reconciled_records:
                entity_ids = [r["entity_id"] for r in reconciled_records]
                txn_entity_result = self.data_fetcher.fetch_txn_entity_data(
                    entity_ids=entity_ids, check_recon_at=True
                )

                if txn_entity_result["success"]:
                    # Get entities that don't have recon_at
                    entities_without_recon_at = {
                        row["entity_id"] for row in txn_entity_result.get("results", [])
                    }

                    # Find records that need update
                    for record in reconciled_records:
                        if record["entity_id"] in entities_without_recon_at:
                            findings.append({
                                "record_id": record["record_id"],
                                "entity_id": record["entity_id"],
                                "recon_at_in_recon_result": record["recon_at"],
                                "issue": "recon_at_not_updated",
                                "suggestion": "Update txn_entity with recon_at timestamp",
                                "recon_result": record["recon_result"],
                            })

            logger.info(
                "Recon_at missing analysis completed",
                total_reconciled=len(reconciled_records),
                findings_count=len(findings),
            )

            return {
                "success": True,
                "findings": findings,
                "total_reconciled": len(reconciled_records),
                "needs_update": len(findings),
                "scenario": "A",
                "scenario_name": "recon_at_not_updated",
            }

        except Exception as e:
            logger.error(
                "Failed to analyze recon_at missing",
                workspace_id=workspace_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "findings": [],
            }

