"""
Data Fetcher for Recon Analysis
Fetches records from journal tables only (not from record tables or APIs).
Uses Trino for Hudi tables or local DB for development.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from src.services.trino_client import TrinoClient
from src.utils.logging import logger
from src.utils.config_reader import get_config_value


class DataFetcher:
    """
    Fetches data from journal tables only (Hudi tables via Trino or local DB).
    All record data comes from journal, not from record tables or APIs.
    """

    def __init__(self):
        """Initialize data fetcher with clients."""
        self.use_local_db = get_config_value("local_db.enabled", False)
        if self.use_local_db:
            from src.data.local_db import get_local_db
            self.local_db = get_local_db()
            self.trino_client = None
        else:
            self.trino_client = TrinoClient()
            self.local_db = None

    def fetch_records(
        self,
        workspace_id: str,
        transaction_date_range: Optional[Tuple[str, str]] = None,
        source_id: Optional[str] = None,
        recon_status: Optional[str] = "Unreconciled",
    ) -> Dict[str, Any]:
        """
        Fetch records from journal tables only (not from record tables or APIs).

        Args:
            workspace_id: Workspace ID
            transaction_date_range: Optional tuple of (start_date, end_date)
            source_id: Optional source ID (file_type_id) filter
            recon_status: Optional recon status filter (default: "Unreconciled")

        Returns:
            Dict containing records separated by internal vs MIS
        """
        try:
            logger.info(
                "Fetching records from journal tables",
                workspace_id=workspace_id,
                date_range=transaction_date_range,
                source_id=source_id,
                recon_status=recon_status,
            )

            # Get file types for this workspace
            from src.analysis.context_enricher import ContextEnricher
            context_enricher = ContextEnricher()
            context = context_enricher.enrich(workspace_id=workspace_id)
            file_types = context.get("file_types", [])

            all_records = []
            internal_records = []
            mis_records = []

            # Fetch records from journal for each file type
            for file_type in file_types:
                file_type_id = file_type.get("id")
                file_type_name = file_type.get("name", "").lower()

                # Filter by source_id if provided
                if source_id and file_type_id != source_id:
                    continue

                journal_result = self.fetch_journal_records(
                    file_type_id=file_type_id,
                    txn_date_start=transaction_date_range[0] if transaction_date_range else None,
                    txn_date_end=transaction_date_range[1] if transaction_date_range else None,
                    recon_status=recon_status,
                )

                if journal_result.get("success"):
                    records = journal_result.get("records", [])
                    all_records.extend(records)

                    # Separate internal vs MIS records
                    if "internal" in file_type_name or "rzp" in file_type_name:
                        internal_records.extend(records)
                    elif "mis" in file_type_name or "bank" in file_type_name:
                        mis_records.extend(records)

            return {
                "success": True,
                "all_records": all_records,
                "internal_records": internal_records,
                "mis_records": mis_records,
                "total_count": len(all_records),
                "internal_count": len(internal_records),
                "mis_count": len(mis_records),
            }

        except Exception as e:
            logger.error(
                "Failed to fetch records from journal",
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
        Fetch recon results from journal tables only (not from APIs).

        Args:
            record_ids: List of record IDs (row_hash or entity_id)
            workspace_id: Workspace ID

        Returns:
            Dict containing recon results from journal
        """
        try:
            logger.info(
                "Fetching recon results from journal tables",
                record_count=len(record_ids),
                workspace_id=workspace_id,
            )

            # Get file types for this workspace
            from src.analysis.context_enricher import ContextEnricher
            context_enricher = ContextEnricher()
            context = context_enricher.enrich(workspace_id=workspace_id)
            file_types = context.get("file_types", [])

            all_results = []

            # Fetch records from journal for each file type
            for file_type in file_types:
                file_type_id = file_type.get("id")

                # Query journal by row_hash or entity_id
                journal_result = self.fetch_journal_records(
                    file_type_id=file_type_id,
                    entity_ids=record_ids,  # Try matching by entity_id
                )

                if journal_result.get("success"):
                    records = journal_result.get("records", [])
                    # Filter by row_hash if available
                    for record in records:
                        if record.get("row_hash") in record_ids or record.get("entity_id") in record_ids:
                            all_results.append(record)

            return {
                "success": True,
                "results": all_results,
                "count": len(all_results),
            }

        except Exception as e:
            logger.error(
                "Failed to fetch recon results from journal",
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
        Fetch txn_entity data from Trino or local DB.

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

            # Use local DB if enabled (transactions table)
            if self.use_local_db and self.local_db:
                transactions = self.local_db.query_transactions(
                    entity_ids=entity_ids,
                    check_reconciled_at=check_recon_at,
                )
                # Convert transactions to txn_entity format
                results = []
                for txn in transactions:
                    results.append({
                        "entity_id": txn.get("entity_id"),
                        "recon_at": txn.get("reconciled_at"),  # reconciled_at maps to recon_at
                        "created_at": txn.get("created_at"),
                        "updated_at": txn.get("updated_at"),
                    })
                return {
                    "success": True,
                    "results": results,
                }
            
            # Use Trino
            if self.trino_client:
                result = self.trino_client.fetch_txn_entity_data(
                    entity_ids=entity_ids, check_recon_at=check_recon_at
                )
                return result
            
            return {
                "success": True,
                "results": [],
                "message": "No data source available",
            }

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

    def fetch_journal_records(
        self,
        file_type_id: str,
        entity_ids: Optional[List[str]] = None,
        txn_date_start: Optional[str] = None,
        txn_date_end: Optional[str] = None,
        recon_status: Optional[str] = None,
        unique_column_value: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch journal records from local DB or Trino (Hudi tables).

        Args:
            file_type_id: File type ID
            entity_ids: Optional list of entity IDs to filter
            txn_date_start: Optional start date for transaction date filter
            txn_date_end: Optional end date for transaction date filter
            recon_status: Optional recon status filter (e.g., 'Unreconciled', 'Reconciled')

        Returns:
            Dict containing journal records
        """
        try:
            logger.info(
                "Fetching journal records",
                file_type_id=file_type_id,
                entity_count=len(entity_ids) if entity_ids else 0,
                date_range=(txn_date_start, txn_date_end),
                recon_status=recon_status,
            )

            # Use local DB if enabled
            if self.use_local_db and self.local_db:
                records = self.local_db.query_journal_records(
                    file_type_id=file_type_id,
                    entity_ids=entity_ids,
                    txn_date_start=txn_date_start,
                    txn_date_end=txn_date_end,
                    recon_status=recon_status,
                    unique_column_value=unique_column_value,
                )
                
                # Convert journal records to a format similar to what recon service returns
                formatted_records = []
                for record in records:
                    # Merge record_data with top-level fields
                    record_data = record.get("record_data", {})
                    formatted_record = {
                        **record_data,
                        "file_type_id": record.get("file_type_id"),
                        "recon_status": record.get("recon_status"),
                        "recon_at": record.get("recon_at"),
                        "entity_id": record.get("entity_id"),
                        "entity_type": record.get("entity_type"),
                        "art_remarks": record.get("art_remarks"),
                        "txn_date": record.get("txn_date"),
                        "row_hash": record.get("row_hash"),
                    }
                    formatted_records.append(formatted_record)
                
                return {
                    "success": True,
                    "records": formatted_records,
                    "count": len(formatted_records),
                }
            
            # Use Trino for Hudi tables (if not using local DB)
            if self.trino_client:
                # Build Trino query for Hudi table
                query = f"SELECT * FROM hudi.recon_pg_prod.{file_type_id} WHERE 1=1"
                params = []
                
                if entity_ids:
                    entity_ids_str = "', '".join(entity_ids)
                    query += f" AND entity_id IN ('{entity_ids_str}')"
                
                if txn_date_start:
                    query += f" AND txn_date >= '{txn_date_start}'"
                
                if txn_date_end:
                    query += f" AND txn_date <= '{txn_date_end}'"
                
                if recon_status:
                    query += f" AND recon_status = '{recon_status}'"
                
                result = self.trino_client.execute_query(query)
                if result.get("success"):
                    return {
                        "success": True,
                        "records": result.get("results", []),
                        "count": len(result.get("results", [])),
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Failed to query Hudi table"),
                        "records": [],
                    }
            
            return {
                "success": False,
                "error": "No data source available (local DB or Trino)",
                "records": [],
            }

        except Exception as e:
            logger.error(
                "Failed to fetch journal records",
                file_type_id=file_type_id,
                error=str(e),
            )
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "records": [],
            }

    def identify_internal_vs_mis(
        self, records: List[Dict[str, Any]], workspace_id: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Identify internal vs MIS records using file_type metadata from ContextEnricher.

        Args:
            records: List of records from journal
            workspace_id: Workspace ID

        Returns:
            Tuple of (internal_records, mis_records)
        """
        try:
            # Get file types from ContextEnricher (uses local DB or Trino, not API)
            from src.analysis.context_enricher import ContextEnricher
            context_enricher = ContextEnricher()
            context = context_enricher.enrich(workspace_id=workspace_id)
            file_types = context.get("file_types", [])

            internal_file_type_ids = set()
            mis_file_type_ids = set()

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
                    # Default classification based on source name (from record_data)
                    record_data = record.get("record_data", {})
                    if isinstance(record_data, dict):
                        source_name = record_data.get("source_name", "").lower()
                    else:
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

