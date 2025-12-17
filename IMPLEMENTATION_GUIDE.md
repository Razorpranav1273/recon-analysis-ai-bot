# Implementation Guide: Rule Analyzer & Gap Analyzer TODOs

## Overview

This guide will help you implement:
1. **Rule Analyzer**: Record pair checking and internal/MIS data fetching
2. **Gap Analyzer**: File ingestion status check

---

## Part 1: Rule Analyzer - Record Pair Checking

### Current Issue (Line 207)
```python
def _has_both_internal_and_mis(self, record, workspace_id):
    # TODO: Implement actual check for record pairs
    return bool(record.get("rzp_entity_id") or record.get("entity_id"))
```

### What We Need to Do

**Goal:** Check if a record has both an internal and MIS counterpart (record pair).

**How Records Are Paired:**
- Records are paired based on:
  - `entity_id` (rzp_entity_id)
  - `transaction_date`
  - `amount` (absolute_amount)
  - `channel_identifier`

**Solution:** Query `recon_result` table or use recon service API to find pairs.

### Implementation Steps

#### Step 1: Add Method to ReconClient

Add this to `src/services/recon_client.py`:

```python
def get_recon_result_by_entity_id(
    self, entity_id: str, workspace_id: str
) -> Dict[str, Any]:
    """
    Get recon results for an entity ID to find record pairs.
    
    Args:
        entity_id: Entity ID (rzp_entity_id)
        workspace_id: Workspace ID
        
    Returns:
        Dict containing recon results with internal and MIS records
    """
    try:
        logger.info(
            "Fetching recon results by entity_id",
            entity_id=entity_id,
            workspace_id=workspace_id,
        )
        
        # Option 1: Use recon_result API if available
        url = f"{self.base_url}/api/v1/recon_results"
        params = {
            "entity_id": entity_id,
            "workspace_id": workspace_id,
        }
        response = self.http_client.get(url, params=params)
        
        if response["success"]:
            results = response.get("data", {}).get("data", [])
            # Separate internal vs MIS
            internal_records = [r for r in results if r.get("is_internal") is True]
            mis_records = [r for r in results if r.get("is_internal") is False]
            
            return {
                "success": True,
                "internal_records": internal_records,
                "mis_records": mis_records,
                "has_both": len(internal_records) > 0 and len(mis_records) > 0,
            }
        
        return {
            "success": False,
            "error": response.get("error", "Failed to fetch recon results"),
            "has_both": False,
        }
        
    except Exception as e:
        logger.error("Failed to get recon results by entity_id", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "has_both": False,
        }
```

#### Step 2: Update `_has_both_internal_and_mis` in RuleAnalyzer

Replace the TODO in `src/analysis/rule_analyzer.py`:

```python
def _has_both_internal_and_mis(
    self, record: Dict[str, Any], workspace_id: str
) -> bool:
    """
    Check if record has both internal and MIS data by querying recon results.
    """
    entity_id = record.get("rzp_entity_id") or record.get("entity_id")
    if not entity_id:
        return False
    
    # Fetch recon results for this entity
    result = self.data_fetcher.recon_client.get_recon_result_by_entity_id(
        entity_id=entity_id,
        workspace_id=workspace_id,
    )
    
    if result["success"]:
        return result.get("has_both", False)
    
    # Fallback: Check if record has both source types
    # This is a simplified check if API doesn't work
    source_id = record.get("source_id")
    file_type_id = record.get("file_type_id")
    
    # Check if we have both internal and MIS file types
    # (This requires fetching file types, which is already done in data_fetcher)
    return bool(entity_id)  # Simplified fallback
```

---

## Part 2: Rule Analyzer - Internal/MIS Data Fetching

### Current Issue (Line 224)
```python
def _get_internal_and_mis_data(self, record, workspace_id):
    # TODO: Implement actual data fetching for internal and MIS records
    entity_id = record.get("rzp_entity_id") or record.get("entity_id")
    return record, record  # Simplified: return same record as both
```

### What We Need to Do

**Goal:** Fetch separate internal and MIS records for a given entity.

**Solution:** Use the same `get_recon_result_by_entity_id` method to get both records.

### Implementation

Update `_get_internal_and_mis_data` in `src/analysis/rule_analyzer.py`:

```python
def _get_internal_and_mis_data(
    self, record: Dict[str, Any], workspace_id: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Get internal and MIS data for a record by fetching recon results.
    """
    entity_id = record.get("rzp_entity_id") or record.get("entity_id")
    if not entity_id:
        return None, None
    
    # Fetch recon results for this entity
    result = self.data_fetcher.recon_client.get_recon_result_by_entity_id(
        entity_id=entity_id,
        workspace_id=workspace_id,
    )
    
    if not result["success"]:
        logger.warning(
            "Failed to fetch recon results for entity",
            entity_id=entity_id,
            error=result.get("error"),
        )
        return None, None
    
    internal_records = result.get("internal_records", [])
    mis_records = result.get("mis_records", [])
    
    # Return first internal and first MIS record
    internal_data = internal_records[0] if internal_records else None
    mis_data = mis_records[0] if mis_records else None
    
    if not internal_data or not mis_data:
        logger.warning(
            "Missing internal or MIS data for entity",
            entity_id=entity_id,
            has_internal=bool(internal_data),
            has_mis=bool(mis_data),
        )
    
    return internal_data, mis_data
```

---

## Part 3: Gap Analyzer - File Ingestion Check

### Current Issue (Line 163)
```python
def _check_internal_file_ingestion(self, workspace_id, transaction_date):
    # TODO: Implement actual file ingestion check via recon service or Trino
    return True  # Placeholder
```

### What We Need to Do

**Goal:** Check if an internal file was ingested for a given transaction date.

**How File Ingestion Works:**
- Files are uploaded and ingested into the system
- `file_detail` table stores file metadata
- `ingestion_run_log` stores ingestion status
- Check if file exists and ingestion status is successful (status_code = 200)

### Implementation Steps

#### Step 1: Add Method to ReconClient

Add this to `src/services/recon_client.py`:

```python
def check_file_ingestion(
    self, workspace_id: str, transaction_date: str, file_type_name: str = "internal"
) -> Dict[str, Any]:
    """
    Check if file was ingested for a given date.
    
    Args:
        workspace_id: Workspace ID
        transaction_date: Transaction date (YYYY-MM-DD)
        file_type_name: File type name filter (e.g., "internal", "rzp")
        
    Returns:
        Dict containing ingestion status
    """
    try:
        logger.info(
            "Checking file ingestion",
            workspace_id=workspace_id,
            transaction_date=transaction_date,
            file_type_name=file_type_name,
        )
        
        # Option 1: Use file_detail API
        url = f"{self.base_url}/api/v1/file_details"
        params = {
            "workspace_id": workspace_id,
            "transaction_date": transaction_date,
        }
        response = self.http_client.get(url, params=params)
        
        if response["success"]:
            file_details = response.get("data", {}).get("data", [])
            
            # Filter for internal file types
            internal_files = []
            for file_detail in file_details:
                file_type = file_detail.get("file_type", {})
                file_type_name_lower = file_type.get("name", "").lower()
                
                if file_type_name.lower() in file_type_name_lower or "internal" in file_type_name_lower:
                    # Check ingestion status
                    ingestion_status = file_detail.get("ingestion_status")
                    if ingestion_status == "processed" or file_detail.get("ingestion_status_code") == 200:
                        internal_files.append(file_detail)
            
            return {
                "success": True,
                "file_ingested": len(internal_files) > 0,
                "file_count": len(internal_files),
                "files": internal_files,
            }
        
        return {
            "success": False,
            "error": response.get("error", "Failed to check file ingestion"),
            "file_ingested": False,
        }
        
    except Exception as e:
        logger.error("Failed to check file ingestion", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "file_ingested": False,
        }
```

#### Step 2: Update `_check_internal_file_ingestion` in GapAnalyzer

Replace the TODO in `src/analysis/gap_analyzer.py`:

```python
def _check_internal_file_ingestion(
    self, workspace_id: str, transaction_date: str
) -> bool:
    """
    Check if internal file was ingested for given date.
    """
    try:
        result = self.data_fetcher.recon_client.check_file_ingestion(
            workspace_id=workspace_id,
            transaction_date=transaction_date,
            file_type_name="internal",
        )
        
        if result["success"]:
            return result.get("file_ingested", False)
        
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
```

---

## Alternative: Using Trino (If API Not Available)

If the recon service APIs don't have these endpoints, you can query Trino directly:

### For Record Pairs (Trino):

```python
# In trino_client.py
def get_record_pairs_by_entity_id(
    self, entity_id: str, workspace_id: str
) -> Dict[str, Any]:
    """Get record pairs from Trino."""
    query = f"""
    SELECT 
        r.id as record_id,
        r.rzp_entity_id,
        r.transaction_date,
        r.absolute_amount,
        r.source_id,
        ft.name as file_type_name,
        rs.is_internal
    FROM record r
    JOIN file_type ft ON r.source_id = ft.source_id
    JOIN recon_state rs ON r.workspace_id = rs.workspace_id
    WHERE r.rzp_entity_id = '{entity_id}'
      AND r.workspace_id = '{workspace_id}'
      AND r.deleted_at IS NULL
    """
    # Execute query and separate internal vs MIS
```

### For File Ingestion (Trino):

```python
# In trino_client.py
def check_file_ingestion_trino(
    self, workspace_id: str, transaction_date: str
) -> Dict[str, Any]:
    """Check file ingestion from Trino."""
    query = f"""
    SELECT 
        fd.id,
        fd.name,
        fd.transaction_date,
        irl.status_code,
        ft.name as file_type_name
    FROM file_detail fd
    JOIN file_type ft ON fd.file_type_id = ft.id
    LEFT JOIN ingestion_run_log irl ON fd.id = irl.file_id
    WHERE fd.workspace_id = '{workspace_id}'
      AND fd.transaction_date = DATE '{transaction_date}'
      AND (ft.name LIKE '%internal%' OR ft.name LIKE '%rzp%')
      AND irl.status_code = 200
    """
    # Execute query and check if results exist
```

---

## Testing Your Implementation

### Test Record Pair Checking:

```python
# Test in Python shell or add to tests
from src.analysis.rule_analyzer import RuleAnalyzer

analyzer = RuleAnalyzer()
record = {"rzp_entity_id": "test_entity_123", "id": "record_123"}
has_both = analyzer._has_both_internal_and_mis(record, "workspace_id")
print(f"Has both: {has_both}")
```

### Test Internal/MIS Data Fetching:

```python
internal, mis = analyzer._get_internal_and_mis_data(record, "workspace_id")
print(f"Internal: {internal}")
print(f"MIS: {mis}")
```

### Test File Ingestion Check:

```python
from src.analysis.gap_analyzer import GapAnalyzer

gap_analyzer = GapAnalyzer()
ingested = gap_analyzer._check_internal_file_ingestion(
    "workspace_id", "2024-01-15"
)
print(f"File ingested: {ingested}")
```

---

## Next Steps

1. **Check API Endpoints**: First, verify if your recon service has these APIs:
   - `/api/v1/recon_results?entity_id=XXX`
   - `/api/v1/file_details?workspace_id=XXX&transaction_date=XXX`

2. **If APIs Exist**: Use the API-based implementation above

3. **If APIs Don't Exist**: Use Trino queries (alternative implementation)

4. **Test**: Run the bot and verify the analysis works correctly

5. **Handle Edge Cases**: 
   - What if entity_id is missing?
   - What if no records found?
   - What if API fails?

---

## Questions to Answer

Before implementing, check:

1. **Does your recon service have a `/recon_results` API?**
   - If yes → Use API
   - If no → Use Trino

2. **Does your recon service have a `/file_details` API?**
   - If yes → Use API
   - If no → Use Trino

3. **What's the actual API response structure?**
   - Check by calling the API manually
   - Adjust parsing logic accordingly

---

**Ready to implement? Start with Part 1 (Record Pair Checking) and test it before moving to Part 2!**

