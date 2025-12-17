"""
Create test scenarios for all three analysis scenarios.
Modifies journal, transactions, and payments tables to create test cases.
"""

from src.data.local_db import get_local_db
from src.utils.logging import logger
import json


def create_scenario_a_data(db):
    """
    Scenario A: Records reconciled in journal but recon_at not updated in transactions.
    - Create some reconciled records in journal (MIS file type: NuSSCThn8s0E05)
    - Remove reconciled_at from corresponding transactions
    """
    logger.info("Creating Scenario A test data")
    
    cursor = db.conn.cursor()
    
    # Get MIS records (NuSSCThn8s0E05) and extract their entity_ids (pay_id)
    cursor.execute("""
        SELECT entity_id, record_data FROM journal 
        WHERE file_type_id = 'NuSSCThn8s0E05' AND txn_date = '2025-12-14'
        LIMIT 2
    """)
    records = cursor.fetchall()
    
    entity_ids_to_update = []
    for entity_id, record_data_str in records:
        try:
            record_data = json.loads(record_data_str) if isinstance(record_data_str, str) else record_data_str
            if isinstance(record_data, dict):
                pay_id = record_data.get('pay_id') or entity_id
                entity_ids_to_update.append((pay_id, entity_id))
        except:
            entity_ids_to_update.append((entity_id, entity_id))
    
    for pay_id, journal_entity_id in entity_ids_to_update:
        # Update journal to Reconciled with recon_at
        cursor.execute("""
            UPDATE journal 
            SET recon_status = 'Reconciled', 
                recon_at = '15/12/2025 07:36:01'
            WHERE entity_id = ? AND file_type_id = 'NuSSCThn8s0E05'
        """, (journal_entity_id,))
        
        # Remove reconciled_at from transactions (Scenario A case)
        cursor.execute("""
            UPDATE transactions 
            SET reconciled_at = NULL
            WHERE entity_id = ?
        """, (pay_id,))
    
    db.conn.commit()
    logger.info("Scenario A data created", count=len(entity_ids_to_update))


def create_scenario_b_data(db):
    """
    Scenario B: MIS records missing internal data.
    - Keep MIS records in journal (NuSSCivzNm01QX - bank_payment_report, has extracted_payment_id)
    - Remove corresponding internal records (NuSSCThn8s0E05 - rzp_payment_report, has pay_id)
    - Some payments exist, some don't (for testing)
    - Some payments have data lag
    """
    logger.info("Creating Scenario B test data")
    
    cursor = db.conn.cursor()
    
    # MIS file type: NuSSCivzNm01QX (bank_payment_report, has extracted_payment_id as unique_column)
    mis_file_type_id = 'NuSSCivzNm01QX'
    
    # Internal file type: NuSSCThn8s0E05 (rzp_payment_report, has pay_id as unique_column)
    internal_file_type_id = 'NuSSCThn8s0E05'
    
    # Get MIS records and extract their entity_ids (extracted_payment_id values)
    cursor.execute("""
        SELECT entity_id, record_data FROM journal 
        WHERE file_type_id = ? AND txn_date = '2025-12-14'
        LIMIT 4
    """, (mis_file_type_id,))
    mis_records = cursor.fetchall()
    
    if not mis_records:
        logger.warning("No MIS records found for Scenario B")
        return
    
    # Extract entity_ids from MIS records (extracted_payment_id from record_data)
    mis_entity_ids = []
    for entity_id, record_data_str in mis_records:
        try:
            record_data = json.loads(record_data_str) if isinstance(record_data_str, str) else record_data_str
            if isinstance(record_data, dict):
                extracted_payment_id = record_data.get('extracted_payment_id') or entity_id
                mis_entity_ids.append(extracted_payment_id)
        except:
            mis_entity_ids.append(entity_id)
    
    # Get internal records and extract their entity_ids (pay_id values)
    cursor.execute("""
        SELECT entity_id, record_data FROM journal 
        WHERE file_type_id = ? AND txn_date = '2025-12-14'
    """, (internal_file_type_id,))
    internal_records = cursor.fetchall()
    
    internal_entity_ids = set()
    for entity_id, record_data_str in internal_records:
        try:
            record_data = json.loads(record_data_str) if isinstance(record_data_str, str) else record_data_str
            if isinstance(record_data, dict):
                pay_id = record_data.get('pay_id') or entity_id
                internal_entity_ids.add(pay_id)
        except:
            internal_entity_ids.add(entity_id)
    
    # Find MIS entities that have matching internal records
    mis_with_internal = []
    for mis_entity_id in mis_entity_ids[:2]:  # Use first 2
        if mis_entity_id in internal_entity_ids:
            mis_with_internal.append(mis_entity_id)
    
    # Delete internal records for these entities (create gap)
    # MIS has extracted_payment_id, Internal has pay_id - they match if values are equal
    for mis_entity_id in mis_with_internal:
        # Find internal record with matching pay_id (internal records have pay_id, not extracted_payment_id)
        cursor.execute("""
            SELECT entity_id, record_data FROM journal 
            WHERE file_type_id = ? AND txn_date = '2025-12-14'
        """, (internal_file_type_id,))
        for (internal_entity_id, record_data_str) in cursor.fetchall():
            try:
                record_data = json.loads(record_data_str) if isinstance(record_data_str, str) else record_data_str
                if isinstance(record_data, dict):
                    pay_id = record_data.get('pay_id')
                    # Match: MIS extracted_payment_id == Internal pay_id
                    if pay_id == mis_entity_id:
                        # Delete this internal record
                        cursor.execute("""
                            DELETE FROM journal 
                            WHERE entity_id = ? AND file_type_id = ?
                        """, (internal_entity_id, internal_file_type_id))
                        logger.info("Deleted internal record", mis_entity_id=mis_entity_id, internal_entity_id=internal_entity_id, pay_id=pay_id)
                        break
            except Exception as e:
                logger.warning(f"Error processing internal record {internal_entity_id}: {e}")
                pass
    
    # Create payment data lag for first entity
    if mis_with_internal:
        entity_id = mis_with_internal[0]
        # Update payment to have significant data lag (>1 hour = 5000 seconds)
        cursor.execute("""
            UPDATE payments 
            SET updated_at = 1765700000,
                _datalake_updated_at = 1765705000
            WHERE id = ?
        """, (entity_id,))
        logger.info("Created data lag", entity_id=entity_id)
        
        # For second entity, remove payment (payment_not_found scenario)
        if len(mis_with_internal) > 1:
            entity_id2 = mis_with_internal[1]
            cursor.execute("""
                DELETE FROM payments 
                WHERE id = ?
            """, (entity_id2,))
            logger.info("Removed payment", entity_id=entity_id2)
    
    db.conn.commit()
    logger.info("Scenario B data created", mis_count=len(mis_with_internal))


def create_scenario_c_data(db):
    """
    Scenario C: Both datasets present but rules not matching.
    - Create unreconciled records with both internal and MIS data
    - Ensure they have mismatched fields that will fail rules
    """
    logger.info("Creating Scenario C test data")
    
    cursor = db.conn.cursor()
    
    # MIS file type: NuSSCivzNm01QX (bank_payment_report, has extracted_payment_id)
    mis_ft_id = 'NuSSCivzNm01QX'
    # Internal file type: NuSSCThn8s0E05 (rzp_payment_report, has pay_id)
    internal_ft_id = 'NuSSCThn8s0E05'
    
    # Find records that have matching entity_ids (MIS extracted_payment_id = Internal pay_id)
    # Get all MIS records
    cursor.execute("""
        SELECT entity_id, record_data FROM journal 
        WHERE file_type_id = ? AND txn_date = '2025-12-14'
    """, (mis_ft_id,))
    mis_records = cursor.fetchall()
    
    # Get all internal records
    cursor.execute("""
        SELECT entity_id, record_data FROM journal 
        WHERE file_type_id = ? AND txn_date = '2025-12-14'
    """, (internal_ft_id,))
    internal_records = cursor.fetchall()
    
    # Find matching pairs by comparing MIS extracted_payment_id and Internal pay_id
    matching_pairs = []
    for mis_entity_id, mis_data_str in mis_records:
        try:
            mis_data = json.loads(mis_data_str) if isinstance(mis_data_str, str) else mis_data_str
            if isinstance(mis_data, dict):
                extracted_payment_id = mis_data.get('extracted_payment_id')
                if extracted_payment_id:
                    # Find internal record with matching pay_id
                    for internal_entity_id, internal_data_str in internal_records:
                        try:
                            internal_data = json.loads(internal_data_str) if isinstance(internal_data_str, str) else internal_data_str
                            if isinstance(internal_data, dict):
                                pay_id = internal_data.get('pay_id')
                                if pay_id == extracted_payment_id:
                                    matching_pairs.append((extracted_payment_id, mis_entity_id, mis_data, internal_entity_id, internal_data))
                                    break
                        except:
                            continue
        except:
            continue
    
    # Create mismatch for first matching pair
    # If no matching pairs found, create new records for Scenario C
    if not matching_pairs:
        # Create new test records for Scenario C
        entity_id = "RrSCENARIO_C_TEST"
        
        # Create MIS record
        mis_record_data = {
            "extracted_payment_id": entity_id,
            "abs_amount": 1000.0,
            "amount": 1000.0,
            "txn_date": "2025-12-14",
            "mpayment_date": "2025-12-14",
        }
        cursor.execute("""
            INSERT INTO journal (file_type_id, entity_id, txn_date, record_data, recon_status)
            VALUES (?, ?, ?, ?, ?)
        """, (mis_ft_id, entity_id, "2025-12-14", json.dumps(mis_record_data), "Unreconciled"))
        
        # Create Internal record with mismatched amount
        internal_record_data = {
            "pay_id": entity_id,
            "abs_amount": 1100.0,  # 10% mismatch
            "amount": 1100.0,
            "txn_date": "2025-12-14",
            "date": "2025-12-14",
        }
        cursor.execute("""
            INSERT INTO journal (file_type_id, entity_id, txn_date, record_data, recon_status)
            VALUES (?, ?, ?, ?, ?)
        """, (internal_ft_id, entity_id, "2025-12-14", json.dumps(internal_record_data), "Unreconciled"))
        
        logger.info("Created new test records for Scenario C", entity_id=entity_id)
    else:
        pay_id, mis_entity_id, mis_data, internal_entity_id, internal_data = matching_pairs[0]
        
        # Get original amounts
        mis_amount = mis_data.get('abs_amount') or mis_data.get('amount') or mis_data.get('mpayment_amt')
        internal_amount = internal_data.get('abs_amount') or internal_data.get('amount') or internal_data.get('mpayment_amt')
        
        # Create 10% mismatch in MIS amount
        if mis_amount:
            new_mis_amount = float(mis_amount) * 1.1  # 10% increase
            mis_data['abs_amount'] = new_mis_amount
            mis_data['amount'] = new_mis_amount
            if 'mpayment_amt' in mis_data:
                mis_data['mpayment_amt'] = new_mis_amount
        
        # Update both records to Unreconciled with mismatched amounts
        cursor.execute("""
            UPDATE journal 
            SET record_data = ?,
                recon_status = 'Unreconciled',
                art_remarks = NULL,
                recon_at = NULL
            WHERE entity_id = ? AND file_type_id = ?
        """, (json.dumps(mis_data), mis_entity_id, mis_ft_id))
        
        # Keep internal with original amount (different from MIS)
        cursor.execute("""
            UPDATE journal 
            SET record_data = ?,
                recon_status = 'Unreconciled',
                art_remarks = NULL,
                recon_at = NULL
            WHERE entity_id = ? AND file_type_id = ?
        """, (json.dumps(internal_data), internal_entity_id, internal_ft_id))
        
        logger.info("Created mismatch", pay_id=pay_id, mis_amount=new_mis_amount if mis_amount else None, internal_amount=internal_amount)
    
    db.conn.commit()
    logger.info("Scenario C data created")


def main():
    """Create test scenarios for all three analysis scenarios."""
    db = get_local_db()
    
    try:
        print("🔧 Creating test scenarios...\n")
        
        print("📋 Scenario A: Reconciled in journal but recon_at missing in transactions")
        create_scenario_a_data(db)
        
        print("\n📋 Scenario B: MIS records missing internal data")
        create_scenario_b_data(db)
        
        print("\n📋 Scenario C: Both datasets present but rules not matching")
        create_scenario_c_data(db)
        
        print("\n✅ All test scenarios created!")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()

