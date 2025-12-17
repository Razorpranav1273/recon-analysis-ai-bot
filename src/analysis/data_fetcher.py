"""
Data Fetcher for Recon Analysis
Fetches records, recon results, and related data from recon service and Trino.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from src.services.recon_client import ReconClient
from src.services.trino_client import TrinoClient
from src.utils.logging import logger


class DataFetcher:
    """
    Fetches data from recon service and Trino for analysis.
    """

    def __init__(self):
        """Initialize data fetcher with clients."""
        self.recon_client = ReconClient()
        self.trino_client = TrinoClient()

    def fetch_records(
        self,
        workspace_id: str,
        transaction_date_range: Optional[Tuple[str, str]] = None,
        source_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch records from recon service.

        Args:
            workspace_id: Workspace ID
            transaction_date_range: Optional tuple of (start_date, end_date)
            source_id: Optional source ID filter

        Returns:
            Dict containing records separated by internal vs MIS
        """
        try:
            logger.info(
                "Fetching records",
                workspace_id=workspace_id,
                date_range=transaction_date_range,
                source_id=source_id,
            )

            # Fetch unreconciled records
            result = self.recon_client.get_unreconciled_records(
                workspace_id=workspace_id,
                source_id=source_id,
                transaction_date=transaction_date_range[0] if transaction_date_range else None,
            )

            if not result["success"]:
                return result

            records = result.get("records", [])

            # Separate internal vs MIS records
            internal_records, mis_records = self.identify_internal_vs_mis(
                records, workspace_id
            )

            return {
                "success": True,
                "all_records": records,
                "internal_records": internal_records,
                "mis_records": mis_records,
                "total_count": len(records),
                "internal_count": len(internal_records),
                "mis_count": len(mis_records),
            }

        except Exception as e:
            logger.error(
                "Failed to fetch records",
                workspace_id=workspace_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "all_records": [],
                "internal_records": [],
                "mis_records": [],
            }

    def fetch_recon_results(
        self, record_ids: List[str], workspace_id: str
    ) -> Dict[str, Any]:
        """
        Fetch recon results for given record IDs.

        Args:
            record_ids: List of record IDs
            workspace_id: Workspace ID

        Returns:
            Dict containing recon results
        """
        try:
            logger.info(
                "Fetching recon results",
                record_count=len(record_ids),
                workspace_id=workspace_id,
            )

            all_results = []
            for record_id in record_ids:
                result = self.recon_client.get_recon_results(
                    record_id=record_id, workspace_id=workspace_id
                )
                if result["success"]:
                    all_results.extend(result.get("results", []))

            return {
                "success": True,
                "results": all_results,
                "count": len(all_results),
            }

        except Exception as e:
            logger.error(
                "Failed to fetch recon results",
                record_count=len(record_ids),
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "results": [],
            }

    def fetch_txn_entity_data(
        self, entity_ids: List[str], check_recon_at: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch txn_entity data from Trino.

        Args:
            entity_ids: List of entity IDs
            check_recon_at: Whether to check for recon_at timestamp

        Returns:
            Dict containing txn_entity data
        """
        try:
            logger.info(
                "Fetching txn_entity data",
                entity_count=len(entity_ids),
                check_recon_at=check_recon_at,
            )

            result = self.trino_client.fetch_txn_entity_data(
                entity_ids=entity_ids, check_recon_at=check_recon_at
            )

            return result

        except Exception as e:
            logger.error(
                "Failed to fetch txn_entity data",
                entity_count=len(entity_ids),
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "results": [],
            }

    def identify_internal_vs_mis(
        self, records: List[Dict[str, Any]], workspace_id: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Identify internal vs MIS records using file_type metadata.

        Args:
            records: List of records
            workspace_id: Workspace ID

        Returns:
            Tuple of (internal_records, mis_records)
        """
        try:
            # Get file types to identify internal vs MIS
            file_types_result = self.recon_client.get_file_types(workspace_id)

            internal_file_type_ids = set()
            mis_file_type_ids = set()

            if file_types_result["success"]:
                file_types = file_types_result.get("file_types", [])
                for file_type in file_types:
                    file_type_name = file_type.get("name", "").lower()
                    file_type_id = file_type.get("id")
                    if "internal" in file_type_name or "rzp" in file_type_name:
                        internal_file_type_ids.add(file_type_id)
                    elif "mis" in file_type_name or "bank" in file_type_name:
                        mis_file_type_ids.add(file_type_id)

            # Separate records
            internal_records = []
            mis_records = []

            for record in records:
                file_type_id = record.get("file_type_id") or record.get("source_id")
                if file_type_id in internal_file_type_ids:
                    internal_records.append(record)
                elif file_type_id in mis_file_type_ids:
                    mis_records.append(record)
                else:
                    # Default classification based on source name
                    source_name = record.get("source_name", "").lower()
                    if "internal" in source_name or "rzp" in source_name:
                        internal_records.append(record)
                    elif "mis" in source_name or "bank" in source_name:
                        mis_records.append(record)

            logger.info(
                "Identified internal vs MIS records",
                total=len(records),
                internal=len(internal_records),
                mis=len(mis_records),
            )

            return internal_records, mis_records

        except Exception as e:
            logger.error("Failed to identify internal vs MIS records", error=str(e))
            # Return all records as unknown if classification fails
            return [], records

