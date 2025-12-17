"""
Load test data into local SQLite database.
"""

import json
import csv
import sqlite3
from pathlib import Path
from typing import Dict, Any, List
from src.data.local_db import LocalDB
from src.utils.logging import logger


def load_workspace_and_file_types(db: LocalDB, data_file: str):
    """Load workspace and file_types from data.json."""
    logger.info("Loading workspace and file_types", file=data_file)
    
    with open(data_file, "r") as f:
        content = f.read()
    
    # Parse the JSON-like structure
    # The file has "workspace:" and "file_types:" markers
    workspace_start = content.find("workspace:")
    file_types_start = content.find("file_types:")
    
    workspace_data = {}
    file_types_data = []
    
    if workspace_start >= 0:
        workspace_end = file_types_start if file_types_start > workspace_start else len(content)
        workspace_str = content[workspace_start + len("workspace:"):workspace_end].strip()
        if workspace_str.startswith("{"):
            workspace_data = json.loads(workspace_str)
    
    if file_types_start >= 0:
        file_types_str = content[file_types_start + len("file_types:"):].strip()
        if file_types_str.startswith("["):
            file_types_data = json.loads(file_types_str)
    
    cursor = db.conn.cursor()
    
    # Insert workspace
    if workspace_data:
        cursor.execute("""
            INSERT OR REPLACE INTO workspaces 
            (id, merchant_id, name, workspace_metadata, reporting_emails, 
             email_cut_off_time, automatic_fetching, migrated_to_hudi, deleted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            workspace_data.get("id"),
            workspace_data.get("merchant_id"),
            workspace_data.get("name"),
            json.dumps(workspace_data.get("workspace_metadata", {})),
            json.dumps(workspace_data.get("reporting_emails", [])),
            workspace_data.get("email_cut_off_time"),
            1 if workspace_data.get("automatic_fetching") else 0,
            1 if workspace_data.get("migrated_to_hudi") else 0,
            None,
        ))
        logger.info("Loaded workspace", workspace_id=workspace_data.get("id"))
    
    # Insert file types
    for ft in file_types_data:
        cursor.execute("""
            INSERT OR REPLACE INTO file_types
            (id, workspace_id, merchant_id, source_id, name, schema, file_metadata,
             validators, transformations, recon_pivot_metadata, source_category, deleted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ft.get("id"),
            ft.get("workspace_id"),
            ft.get("merchant_id"),
            ft.get("source_id"),
            ft.get("name"),
            json.dumps(ft.get("schema", {})),
            json.dumps(ft.get("file_metadata", [])),
            json.dumps(ft.get("validators", [])),
            json.dumps(ft.get("transformations", {})),
            json.dumps(ft.get("recon_pivot_metadata", {})),
            ft.get("source_category"),
            None,
        ))
    
    db.conn.commit()
    logger.info("Loaded file types", count=len(file_types_data))


def load_rules_and_rule_recon_state_map(db: LocalDB, csv_file: str):
    """Load rules and rule_recon_state_map from CSV."""
    logger.info("Loading rules and rule_recon_state_map", file=csv_file)
    
    cursor = db.conn.cursor()
    
    # First, we need to load recon_state data
    # For now, we'll extract unique recon_state_ids and create placeholder states
    recon_state_ids = set()
    
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # Find rule_recon_state_map section
    rrsm_start = None
    rules_start = None
    
    for i, row in enumerate(rows):
        if row and row[0]:
            row0_lower = row[0].strip().lower()
            if "rule_recon_state_map" in row0_lower:
                rrsm_start = i + 2  # Skip header row
            elif row0_lower == "rules" or row0_lower.startswith("rules "):
                rules_start = i + 2  # Skip header row
                break
    
    # Load rule_recon_state_map
    rrsm_count = 0
    if rrsm_start and rules_start:
        # Get headers
        headers = rows[rrsm_start - 1]
        
        for i in range(rrsm_start, rules_start - 1):
            row = rows[i]
            if not row or not row[0] or not row[0].strip():  # Skip empty rows
                continue
            
            # Map row to dict
            rrsm = dict(zip(headers, row))
            
            # Skip if no ID
            if not rrsm.get("id"):
                continue
            
            # Collect recon_state_id
            if rrsm.get("recon_state_id"):
                try:
                    recon_state_ids.add(int(rrsm["recon_state_id"]))
                except (ValueError, TypeError):
                    pass
            
            # Insert rule_recon_state_map
            try:
                # Safely parse integers
                def safe_int(value, default=None):
                    if not value or not str(value).strip():
                        return default
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        return default
                
                cursor.execute("""
                    INSERT OR REPLACE INTO rule_recon_state_map
                    (id, merchant_id, workspace_id, rule_expression, file_type1_id, file_type2_id,
                     recon_state_id, created_at, updated_at, deleted_at, seq_number, workflow_id,
                     job_context_id, is_unreconciled_enrichment_rule)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    safe_int(rrsm.get("id")),
                    rrsm.get("merchant_id"),
                    rrsm.get("workspace_id"),
                    rrsm.get("rule_expression"),
                    rrsm.get("file_type1_id"),
                    rrsm.get("file_type2_id"),
                    safe_int(rrsm.get("recon_state_id")),
                    safe_int(rrsm.get("created_at")),
                    safe_int(rrsm.get("updated_at")),
                    rrsm.get("deleted_at") or None,
                    safe_int(rrsm.get("seq_number")),
                    rrsm.get("workflow_id"),
                    rrsm.get("job_context_id"),
                    1 if str(rrsm.get("is_unreconciled_enrichment_rule", "")).upper() == "TRUE" else 0,
                ))
                rrsm_count += 1
            except Exception as e:
                logger.warning("Failed to insert rule_recon_state_map row", row=rrsm.get("id"), error=str(e))
        
        logger.info("Loaded rule_recon_state_map", count=rrsm_count)
    
    # Load rules
    rules_count = 0
    if rules_start:
        headers = rows[rules_start - 1]
        
        for i in range(rules_start, len(rows)):
            row = rows[i]
            if not row or not row[0] or not row[0].strip():  # Skip empty rows
                continue
            
            rule = dict(zip(headers, row))
            
            # Skip if no ID
            if not rule.get("id"):
                continue
            
            # Insert rule
            try:
                # Safely parse integers
                def safe_int(value, default=None):
                    if not value or not str(value).strip():
                        return default
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        return default
                
                cursor.execute("""
                    INSERT OR REPLACE INTO rules
                    (id, workspace_id, merchant_id, rule, file_type1_id, file_type2_id,
                     is_self_rule, created_at, updated_at, deleted_at, job_context_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    safe_int(rule.get("id")),
                    rule.get("workspace_id"),
                    rule.get("merchant_id"),
                    rule.get("rule"),
                    rule.get("file_type1_id"),
                    rule.get("file_type2_id"),
                    1 if str(rule.get("is_self_rule", "")).upper() == "TRUE" else 0,
                    safe_int(rule.get("created_at")),
                    safe_int(rule.get("updated_at")),
                    rule.get("deleted_at") or None,
                    rule.get("job_context_id"),
                ))
                rules_count += 1
            except Exception as e:
                logger.warning("Failed to insert rule row", row=rule.get("id"), error=str(e))
        
        logger.info("Loaded rules", count=rules_count)
    
    # Create placeholder recon_state entries
    for state_id in recon_state_ids:
        cursor.execute("""
            INSERT OR IGNORE INTO recon_state
            (id, state, rank, is_internal, parent_id, art_remarks, deleted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            state_id,
            f"State_{state_id}",  # Placeholder
            0,
            0,
            None,
            None,
            None,
        ))
    
    db.conn.commit()
    logger.info("Loaded recon_state entries", count=len(recon_state_ids))


def load_journal_data(db: LocalDB, csv_file: str):
    """Load journal/record data from CSV."""
    logger.info("Loading journal data", file=csv_file)
    
    cursor = db.conn.cursor()
    
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    current_file_type_id = None
    headers = None
    record_count = 0
    
    for i, row in enumerate(rows):
        if not row or not row[0]:
            continue
        
        # Check if this is a file_type_id marker
        if row[0].startswith("file_type_id="):
            current_file_type_id = row[0].split("=")[1]
            # Next row should be headers
            if i + 1 < len(rows):
                headers = rows[i + 1]
            continue
        
        # Skip header rows
        if headers and row == headers:
            continue
        
        # If we have headers and file_type_id, process data row
        if headers and current_file_type_id and len(row) >= len(headers):
            # Create record_data dict from all columns except special ones
            record_data = {}
            special_fields = {
                "recon_status": None,
                "recon_at": None,
                "entity_id": None,
                "entity_type": None,
                "art_remarks": None,
                "txn_date": None,
                "row_hash": None,
            }
            
            for j, header in enumerate(headers):
                if j < len(row):
                    value = row[j] if row[j] else None
                    if header in special_fields:
                        special_fields[header] = value
                    else:
                        record_data[header] = value
            
            # Insert journal record
            cursor.execute("""
                INSERT OR REPLACE INTO journal
                (file_type_id, record_data, recon_status, recon_at, entity_id,
                 entity_type, art_remarks, txn_date, row_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                current_file_type_id,
                json.dumps(record_data),
                special_fields["recon_status"],
                special_fields["recon_at"],
                special_fields["entity_id"],
                special_fields["entity_type"],
                special_fields["art_remarks"],
                special_fields["txn_date"],
                special_fields["row_hash"],
            ))
            record_count += 1
    
    db.conn.commit()
    logger.info("Loaded journal records", count=record_count)


def load_transactions_data(db: LocalDB, csv_file: str):
    """Load transactions data from CSV."""
    logger.info("Loading transactions data", file=csv_file)
    
    cursor = db.conn.cursor()
    
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    if not rows:
        logger.warning("No data in transactions CSV")
        return
    
    # First row is headers
    headers = rows[0]
    
    # Key fields we want to store directly
    key_fields = {
        "id", "entity_id", "merchant_id", "type", "amount", "fee", 
        "currency", "reconciled_at", "reconciled_type", "created_at", 
        "updated_at", "created_date"
    }
    
    transaction_count = 0
    
    for i, row in enumerate(rows[1:], 1):  # Skip header
        if not row or not row[0]:  # Skip empty rows
            continue
        
        # Map row to dict
        transaction = dict(zip(headers, row))
        
        # Skip if no ID
        if not transaction.get("id"):
            continue
        
        # Separate key fields from other data
        key_data = {}
        other_data = {}
        
        for key, value in transaction.items():
            if key in key_fields:
                key_data[key] = value
            else:
                other_data[key] = value
        
        # Safely parse integers
        def safe_int(value, default=None):
            if not value or not str(value).strip():
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO transactions
                (id, entity_id, merchant_id, type, amount, fee, currency,
                 reconciled_at, reconciled_type, created_at, updated_at, created_date, other_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                key_data.get("id"),
                key_data.get("entity_id"),
                key_data.get("merchant_id"),
                key_data.get("type"),
                safe_int(key_data.get("amount")),
                safe_int(key_data.get("fee")),
                key_data.get("currency"),
                key_data.get("reconciled_at"),
                key_data.get("reconciled_type"),
                safe_int(key_data.get("created_at")),
                safe_int(key_data.get("updated_at")),
                key_data.get("created_date"),
                json.dumps(other_data) if other_data else None,
            ))
            transaction_count += 1
        except Exception as e:
            logger.warning("Failed to insert transaction row", row=key_data.get("id"), error=str(e))
    
    db.conn.commit()
    logger.info("Loaded transactions", count=transaction_count)


def load_payments_data(db: LocalDB, csv_file: str):
    """Load payments data from CSV."""
    logger.info("Loading payments data", file=csv_file)
    
    cursor = db.conn.cursor()
    
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    if not rows:
        logger.warning("No data in payments CSV")
        return
    
    # First row is headers
    headers = rows[0]
    
    # Key fields we want to store directly
    key_fields = {
        "id", "merchant_id", "amount", "currency", "method", "status",
        "created_at", "updated_at", "_datalake_updated_at", "created_date"
    }
    
    payment_count = 0
    
    for i, row in enumerate(rows[1:], 1):  # Skip header
        if not row or not row[0]:  # Skip empty rows
            continue
        
        # Map row to dict
        payment = dict(zip(headers, row))
        
        # Skip if no ID
        if not payment.get("id"):
            continue
        
        # Separate key fields from other data
        key_data = {}
        other_data = {}
        
        for key, value in payment.items():
            if key in key_fields:
                key_data[key] = value
            else:
                other_data[key] = value
        
        # Safely parse integers
        def safe_int(value, default=None):
            if not value or not str(value).strip():
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO payments
                (id, merchant_id, amount, currency, method, status,
                 created_at, updated_at, _datalake_updated_at, created_date, other_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                key_data.get("id"),
                key_data.get("merchant_id"),
                safe_int(key_data.get("amount")),
                key_data.get("currency"),
                key_data.get("method"),
                key_data.get("status"),
                safe_int(key_data.get("created_at")),
                safe_int(key_data.get("updated_at")),
                safe_int(key_data.get("_datalake_updated_at")),
                key_data.get("created_date"),
                json.dumps(other_data) if other_data else None,
            ))
            payment_count += 1
        except Exception as e:
            logger.warning("Failed to insert payment row", row=key_data.get("id"), error=str(e))
    
    db.conn.commit()
    logger.info("Loaded payments", count=payment_count)


def main():
    """Main function to load all test data."""
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data" / "raw"
    
    data_file = data_dir / "data.json"
    rules_file = data_dir / "recon_rules.csv"
    journal_file = data_dir / "journal_data.csv"
    transactions_file = data_dir / "transactions_db.csv"
    payments_file = data_dir / "payments.csv"
    
    db = LocalDB()
    
    try:
        if data_file.exists():
            load_workspace_and_file_types(db, str(data_file))
        else:
            logger.warning("data.json not found", path=str(data_file))
        
        if rules_file.exists():
            load_rules_and_rule_recon_state_map(db, str(rules_file))
        else:
            logger.warning("recon_rules CSV not found", path=str(rules_file))
        
        if journal_file.exists():
            load_journal_data(db, str(journal_file))
        else:
            logger.warning("Journal CSV not found", path=str(journal_file))
        
        if transactions_file.exists():
            load_transactions_data(db, str(transactions_file))
        else:
            logger.warning("Transactions CSV not found", path=str(transactions_file))
        
        if payments_file.exists():
            load_payments_data(db, str(payments_file))
        else:
            logger.warning("Payments CSV not found", path=str(payments_file))
        
        logger.info("Test data loading completed")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()

