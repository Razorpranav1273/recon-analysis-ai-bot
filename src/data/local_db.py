"""
Local SQLite Database for Test Data
Stores workspace, file_types, rules, rule_recon_state_map, recon_state, and journal data.
"""

import sqlite3
import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from src.utils.logging import logger


class LocalDB:
    """
    Local SQLite database for test data.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize local database.

        Args:
            db_path: Path to SQLite database file. Defaults to local_db.sqlite in project root.
        """
        if db_path is None:
            project_root = Path(__file__).parent.parent.parent
            db_path = str(project_root / "local_db.sqlite")
        
        self.db_path = db_path
        self.conn = None
        self._initialize_database()

    def _initialize_database(self):
        """Create database and tables if they don't exist."""
        # Allow connections to be used across threads (required for Flask)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Return rows as dict-like objects
        
        cursor = self.conn.cursor()
        
        # Create workspaces table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                merchant_id TEXT,
                name TEXT,
                workspace_metadata TEXT,
                reporting_emails TEXT,
                email_cut_off_time TEXT,
                automatic_fetching INTEGER,
                migrated_to_hudi INTEGER,
                deleted_at TEXT
            )
        """)
        
        # Create file_types table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_types (
                id TEXT PRIMARY KEY,
                workspace_id TEXT,
                merchant_id TEXT,
                source_id TEXT,
                name TEXT,
                schema TEXT,
                file_metadata TEXT,
                validators TEXT,
                transformations TEXT,
                recon_pivot_metadata TEXT,
                source_category TEXT,
                deleted_at TEXT,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            )
        """)
        
        # Create rules table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY,
                workspace_id TEXT,
                merchant_id TEXT,
                rule TEXT,
                file_type1_id TEXT,
                file_type2_id TEXT,
                is_self_rule INTEGER,
                created_at INTEGER,
                updated_at INTEGER,
                deleted_at TEXT,
                job_context_id TEXT,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            )
        """)
        
        # Create recon_state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recon_state (
                id INTEGER PRIMARY KEY,
                state TEXT,
                rank INTEGER,
                is_internal INTEGER,
                parent_id INTEGER,
                art_remarks TEXT,
                deleted_at TEXT
            )
        """)
        
        # Create rule_recon_state_map table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rule_recon_state_map (
                id INTEGER PRIMARY KEY,
                merchant_id TEXT,
                workspace_id TEXT,
                rule_expression TEXT,
                file_type1_id TEXT,
                file_type2_id TEXT,
                recon_state_id INTEGER,
                created_at INTEGER,
                updated_at INTEGER,
                deleted_at TEXT,
                seq_number INTEGER,
                workflow_id TEXT,
                job_context_id TEXT,
                is_unreconciled_enrichment_rule INTEGER,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (recon_state_id) REFERENCES recon_state(id)
            )
        """)
        
        # Create journal table (for records from Hudi)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS journal (
                file_type_id TEXT,
                _hoodie_commit_time TEXT,
                _hoodie_commit_seqno TEXT,
                _hoodie_record_key TEXT,
                _hoodie_partition_path TEXT,
                _hoodie_file_name TEXT,
                -- Dynamic columns stored as JSON
                record_data TEXT,
                recon_status TEXT,
                recon_at TEXT,
                entity_id TEXT,
                entity_type TEXT,
                art_remarks TEXT,
                txn_date TEXT,
                row_hash TEXT,
                PRIMARY KEY (file_type_id, entity_id, txn_date)
            )
        """)
        
        # Create transactions table (for checking reconciled_at)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                entity_id TEXT,
                merchant_id TEXT,
                type TEXT,
                amount INTEGER,
                fee INTEGER,
                currency TEXT,
                reconciled_at TEXT,
                reconciled_type TEXT,
                created_at INTEGER,
                updated_at INTEGER,
                created_date TEXT,
                -- Store all other fields as JSON
                other_data TEXT
            )
        """)
        
        # Create payments table (for checking if payment exists and data lag)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id TEXT PRIMARY KEY,
                merchant_id TEXT,
                amount INTEGER,
                currency TEXT,
                method TEXT,
                status TEXT,
                created_at INTEGER,
                updated_at INTEGER,
                _datalake_updated_at INTEGER,
                created_date TEXT,
                -- Store all other fields as JSON
                other_data TEXT
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_types_workspace ON file_types(workspace_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_workspace ON rules(workspace_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rrsm_workspace ON rule_recon_state_map(workspace_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_file_type ON journal(file_type_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_entity ON journal(entity_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_txn_date ON journal(txn_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_entity ON transactions(entity_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_reconciled_at ON transactions(reconciled_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_entity ON transactions(entity_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_reconciled_at ON transactions(reconciled_at)")
        
        self.conn.commit()
        logger.info("Local database initialized", db_path=self.db_path)

    def get_unique_column(self, file_type_id: str) -> Optional[str]:
        """Extract unique_column from file_type metadata."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT file_metadata FROM file_types WHERE id = ?", (file_type_id,))
        row = cursor.fetchone()
        if row:
            file_metadata_str = row[0]
            try:
                file_metadata = json.loads(file_metadata_str) if isinstance(file_metadata_str, str) else file_metadata_str
                if isinstance(file_metadata, list):
                    for meta in file_metadata:
                        if isinstance(meta, dict) and meta.get("name") == "unique_column":
                            return meta.get("value")
            except (json.JSONDecodeError, TypeError):
                pass
        return None

    def query_workspace_by_name(self, workspace_name: str) -> Optional[Dict[str, Any]]:
        """
        Query workspace by name.
        
        Args:
            workspace_name: Name of the workspace
            
        Returns:
            Dict containing workspace data or None if not found
        """
        cursor = self.conn.cursor()
        # Case-insensitive search
        cursor.execute(
            "SELECT * FROM workspaces WHERE UPPER(name) = UPPER(?) AND deleted_at IS NULL",
            (workspace_name,)
        )
        row = cursor.fetchone()
        if row:
            result = dict(row)
            # Parse JSON fields
            if result.get("workspace_metadata"):
                try:
                    result["workspace_metadata"] = json.loads(result["workspace_metadata"])
                except (json.JSONDecodeError, TypeError):
                    pass
            if result.get("reporting_emails"):
                try:
                    result["reporting_emails"] = json.loads(result["reporting_emails"])
                except (json.JSONDecodeError, TypeError):
                    pass
            return result
        return None

    def query_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Query workspace by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM workspaces WHERE id = ? AND deleted_at IS NULL", (workspace_id,))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            # Parse JSON fields
            for json_field in ["workspace_metadata", "reporting_emails"]:
                if result.get(json_field):
                    try:
                        result[json_field] = json.loads(result[json_field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            return result
        return None

    def query_file_types(self, workspace_id: str, file_type_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Query file types for workspace."""
        cursor = self.conn.cursor()
        if file_type_ids:
            placeholders = ",".join("?" * len(file_type_ids))
            query = f"""
                SELECT * FROM file_types 
                WHERE workspace_id = ? AND deleted_at IS NULL
                AND id IN ({placeholders})
            """
            cursor.execute(query, [workspace_id] + file_type_ids)
        else:
            cursor.execute(
                "SELECT * FROM file_types WHERE workspace_id = ? AND deleted_at IS NULL",
                (workspace_id,)
            )
        
        rows = cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            # Parse JSON fields
            for json_field in ["schema", "file_metadata", "validators", "transformations", "recon_pivot_metadata"]:
                if result.get(json_field):
                    try:
                        result[json_field] = json.loads(result[json_field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            results.append(result)
        return results

    def query_rules(self, workspace_id: str, file_type_ids: Optional[List[str]] = None) -> Dict[int, Dict[str, Any]]:
        """Query rules for workspace, returned as dict keyed by rule ID."""
        cursor = self.conn.cursor()
        if file_type_ids:
            placeholders = ",".join("?" * len(file_type_ids))
            query = f"""
                SELECT * FROM rules 
                WHERE workspace_id = ? AND deleted_at IS NULL
                AND (file_type1_id IN ({placeholders}) OR file_type2_id IN ({placeholders}))
            """
            cursor.execute(query, [workspace_id] + file_type_ids + file_type_ids)
        else:
            cursor.execute(
                "SELECT * FROM rules WHERE workspace_id = ? AND deleted_at IS NULL",
                (workspace_id,)
            )
        
        rows = cursor.fetchall()
        rules_dict = {}
        for row in rows:
            rule = dict(row)
            rules_dict[rule["id"]] = rule
        return rules_dict

    def query_rule_recon_state_map(
        self, workspace_id: str, file_type_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Query rule_recon_state_map with recon_state joined."""
        cursor = self.conn.cursor()
        if file_type_ids:
            placeholders = ",".join("?" * len(file_type_ids))
            query = f"""
                SELECT 
                    rrsm.*,
                    rs.state as recon_state,
                    rs.art_remarks,
                    rs.rank,
                    rs.is_internal,
                    rs.parent_id
                FROM rule_recon_state_map rrsm
                JOIN recon_state rs ON rrsm.recon_state_id = rs.id
                WHERE rrsm.workspace_id = ? 
                AND rrsm.deleted_at IS NULL
                AND rs.deleted_at IS NULL
                AND (
                    (rrsm.file_type1_id IN ({placeholders}) AND rrsm.file_type2_id IN ({placeholders}))
                    OR (rrsm.file_type1_id = rrsm.file_type2_id AND rrsm.file_type1_id IN ({placeholders}))
                )
                ORDER BY rrsm.seq_number
            """
            cursor.execute(query, [workspace_id] + file_type_ids + file_type_ids + file_type_ids)
        else:
            query = """
                SELECT 
                    rrsm.*,
                    rs.state as recon_state,
                    rs.art_remarks,
                    rs.rank,
                    rs.is_internal,
                    rs.parent_id
                FROM rule_recon_state_map rrsm
                JOIN recon_state rs ON rrsm.recon_state_id = rs.id
                WHERE rrsm.workspace_id = ? 
                AND rrsm.deleted_at IS NULL
                AND rs.deleted_at IS NULL
                ORDER BY rrsm.seq_number
            """
            cursor.execute(query, (workspace_id,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def query_journal_records(
        self,
        file_type_id: str,
        entity_ids: Optional[List[str]] = None,
        txn_date_start: Optional[str] = None,
        txn_date_end: Optional[str] = None,
        recon_status: Optional[str] = None,
        unique_column_value: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query journal records.
        
        Args:
            file_type_id: File type ID
            entity_ids: Optional list of entity IDs
            txn_date_start: Optional start date
            txn_date_end: Optional end date
            recon_status: Optional recon status filter
            unique_column_value: Optional unique column value (extracted from record_data)
        """
        cursor = self.conn.cursor()
        conditions = ["file_type_id = ?"]
        params = [file_type_id]
        
        if entity_ids:
            placeholders = ",".join("?" * len(entity_ids))
            conditions.append(f"entity_id IN ({placeholders})")
            params.extend(entity_ids)
        
        if txn_date_start:
            conditions.append("txn_date >= ?")
            params.append(txn_date_start)
        
        if txn_date_end:
            conditions.append("txn_date <= ?")
            params.append(txn_date_end)
        
        if recon_status:
            conditions.append("recon_status = ?")
            params.append(recon_status)
        
        if unique_column_value:
            # Get unique column for this file_type
            unique_col = self.get_unique_column(file_type_id)
            if unique_col:
                # Query records where record_data JSON contains the unique_column_value
                # We'll filter in Python after fetching since SQLite JSON support is limited
                pass  # Will filter after fetching
        
        query = f"SELECT * FROM journal WHERE {' AND '.join(conditions)}"
        cursor.execute(query, params)
        
        rows = cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            # Parse record_data JSON
            if result.get("record_data"):
                try:
                    result["record_data"] = json.loads(result["record_data"])
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Filter by unique_column_value if provided
            if unique_column_value:
                unique_col = self.get_unique_column(file_type_id)
                if unique_col and result.get("record_data"):
                    record_data = result["record_data"]
                    if isinstance(record_data, dict):
                        # Check if unique column value matches
                        if record_data.get(unique_col) != unique_column_value:
                            continue
            
            results.append(result)
        return results

    def query_journal_by_unique_column(
        self,
        workspace_id: str,
        unique_column_value: str,
        file_type_ids: Optional[List[str]] = None,
        txn_date_start: Optional[str] = None,
        txn_date_end: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Query journal records across multiple file_types using unique_column value.
        
        This is used to join MIS and Internal data through the unique column.
        
        Args:
            workspace_id: Workspace ID
            unique_column_value: Value of the unique column to search for
            file_type_ids: Optional list of file type IDs to query
            txn_date_start: Optional start date
            txn_date_end: Optional end date
        
        Returns:
            Dict mapping file_type_id to list of matching records
        """
        # Get file types for this workspace
        if not file_type_ids:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT id FROM file_types WHERE workspace_id = ? AND deleted_at IS NULL",
                (workspace_id,)
            )
            file_type_ids = [row[0] for row in cursor.fetchall()]
        
        results = {}
        for file_type_id in file_type_ids:
            unique_col = self.get_unique_column(file_type_id)
            if not unique_col:
                continue
            
            # Query journal records and filter by unique column value
            records = self.query_journal_records(
                file_type_id=file_type_id,
                txn_date_start=txn_date_start,
                txn_date_end=txn_date_end,
            )
            
            # Filter by unique column value
            matching_records = []
            for record in records:
                record_data = record.get("record_data", {})
                if isinstance(record_data, dict):
                    if record_data.get(unique_col) == unique_column_value:
                        matching_records.append(record)
            
            if matching_records:
                results[file_type_id] = matching_records
        
        return results

    def query_transactions(
        self,
        entity_ids: Optional[List[str]] = None,
        check_reconciled_at: bool = True,
        reconciled_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query transactions."""
        cursor = self.conn.cursor()
        conditions = []
        params = []
        
        if entity_ids:
            placeholders = ",".join("?" * len(entity_ids))
            conditions.append(f"entity_id IN ({placeholders})")
            params.extend(entity_ids)
        
        if check_reconciled_at:
            conditions.append("reconciled_at IS NULL")
        
        if reconciled_type:
            conditions.append("reconciled_type = ?")
            params.append(reconciled_type)
        
        query = "SELECT * FROM transactions"
        if conditions:
            query += f" WHERE {' AND '.join(conditions)}"
        
        cursor.execute(query, params)
        
        rows = cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            # Parse other_data JSON
            if result.get("other_data"):
                try:
                    other_data = json.loads(result["other_data"])
                    result.update(other_data)
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(result)
        return results

    def query_payments(
        self,
        payment_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Query payments."""
        cursor = self.conn.cursor()
        conditions = []
        params = []
        
        if payment_ids:
            placeholders = ",".join("?" * len(payment_ids))
            conditions.append(f"id IN ({placeholders})")
            params.extend(payment_ids)
        
        query = "SELECT * FROM payments"
        if conditions:
            query += f" WHERE {' AND '.join(conditions)}"
        
        cursor.execute(query, params)
        
        rows = cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            # Parse other_data JSON
            if result.get("other_data"):
                try:
                    other_data = json.loads(result["other_data"])
                    result.update(other_data)
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(result)
        return results

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global instance
_local_db_instance = None


def get_local_db(db_path: Optional[str] = None) -> LocalDB:
    """
    Get or create global local database instance.

    Args:
        db_path: Optional path to database file

    Returns:
        LocalDB instance
    """
    global _local_db_instance
    if _local_db_instance is None:
        _local_db_instance = LocalDB(db_path)
    return _local_db_instance

