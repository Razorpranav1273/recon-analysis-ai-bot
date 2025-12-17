"""
Test the unified analyzer with all three scenarios.
"""

from src.analysis.unified_analyzer import UnifiedAnalyzer
from src.data.load_test_data import main as load_test_data
from src.data.local_db import get_local_db
from src.data.create_test_scenarios import create_scenario_a_data, create_scenario_b_data, create_scenario_c_data

WORKSPACE_ID = "NuSS853m4g0FSz"
WORKSPACE_NAME = "NETBANKING_AIUSF"


def test_unified_analyzer_scenario_a():
    """Test Scenario A using unified analyzer."""
    print("\n" + "="*70)
    print("UNIFIED ANALYZER - SCENARIO A: Reconciled but recon_at missing")
    print("="*70)
    
    analyzer = UnifiedAnalyzer()
    
    # Find a record that is reconciled - use Internal file type since that's what Scenario A updates
    from src.data.local_db import get_local_db
    import json
    db = get_local_db()
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT j.entity_id, j.file_type_id, j.record_data
        FROM journal j
        LEFT JOIN transactions t ON j.entity_id = t.entity_id
        WHERE j.recon_status = 'Reconciled' AND (t.reconciled_at IS NULL OR t.reconciled_at = '')
        LIMIT 1
    ''')
    record = cursor.fetchone()
    
    if not record:
        print("❌ No test data found for Scenario A")
        return False
    
    entity_id, ft_id, record_data_str = record
    record_data = json.loads(record_data_str) if isinstance(record_data_str, str) else record_data_str
    unique_col = db.get_unique_column(ft_id)
    unique_value = record_data.get(unique_col) if unique_col and isinstance(record_data, dict) else entity_id
    
    # Get file type name
    from src.analysis.context_enricher import ContextEnricher
    context_enricher = ContextEnricher()
    context = context_enricher.enrich(workspace_id=WORKSPACE_ID)
    file_types = context.get("file_types", [])
    file_type_name = None
    for ft in file_types:
        if ft.get("id") == ft_id:
            file_type_name = ft.get("name")
            break
    
    if not file_type_name:
        print(f"❌ Could not find file type name for {ft_id}")
        return False
    
    print(f"   Using entity_id: {entity_id}, unique_value: {unique_value}, file_type: {file_type_name}")
    
    # Use an entity_id that should be reconciled
    result = analyzer.analyze(
        workspace_id=WORKSPACE_ID,
        file_type_name=file_type_name,
        unique_column_value=unique_value,
        transaction_date_range=("2025-12-14", "2025-12-14")
    )
    
    if result.get("success"):
        findings = result.get("findings", [])
        scenarios = result.get("scenarios_detected", [])
        print(f"\n✅ Analysis completed")
        print(f"   Scenarios detected: {scenarios}")
        print(f"   Findings: {len(findings)}")
        print(f"   File type records: {result.get('file_type_records', {})}")
        
        scenario_a_findings = [f for f in findings if f.get("scenario") == "A"]
        print(f"\n   Scenario A findings: {len(scenario_a_findings)}")
        for i, finding in enumerate(scenario_a_findings[:2], 1):
            print(f"\n   Finding {i}:")
            print(f"      Entity ID: {finding.get('entity_id')}")
            print(f"      File Type: {finding.get('file_type_id')}")
            print(f"      Issue: {finding.get('issue')}")
    else:
        print(f"❌ Analysis failed: {result.get('error')}")
    
    return result.get("success") and "A" in result.get("scenarios_detected", [])


def test_unified_analyzer_scenario_b():
    """Test Scenario B using unified analyzer."""
    print("\n" + "="*70)
    print("UNIFIED ANALYZER - SCENARIO B: MIS only, no Internal")
    print("="*70)
    
    analyzer = UnifiedAnalyzer()
    
    # Use an entity_id that should have MIS but no Internal
    result = analyzer.analyze(
        workspace_id=WORKSPACE_ID,
        file_type_name="bank_payment_report",
        unique_column_value="RrW6cHykuVRBUv",  # This should have MIS but no Internal
        transaction_date_range=("2025-12-14", "2025-12-14")
    )
    
    if result.get("success"):
        findings = result.get("findings", [])
        scenarios = result.get("scenarios_detected", [])
        print(f"\n✅ Analysis completed")
        print(f"   Scenarios detected: {scenarios}")
        print(f"   Findings: {len(findings)}")
        print(f"   File type records: {result.get('file_type_records', {})}")
        
        scenario_b_findings = [f for f in findings if f.get("scenario") == "B"]
        print(f"\n   Scenario B findings: {len(scenario_b_findings)}")
        for i, finding in enumerate(scenario_b_findings[:2], 1):
            print(f"\n   Finding {i}:")
            print(f"      Entity ID: {finding.get('entity_id')}")
            print(f"      Issue: {finding.get('issue')}")
            print(f"      Payment exists: {finding.get('payment_exists')}")
            print(f"      Data lag detected: {finding.get('data_lag_detected')}")
    else:
        print(f"❌ Analysis failed: {result.get('error')}")
    
    return result.get("success") and "B" in result.get("scenarios_detected", [])


def test_unified_analyzer_scenario_c():
    """Test Scenario C using unified analyzer."""
    print("\n" + "="*70)
    print("UNIFIED ANALYZER - SCENARIO C: Both present but unreconciled")
    print("="*70)
    
    analyzer = UnifiedAnalyzer()
    
    # Use an entity_id that should have both MIS and Internal but unreconciled
    result = analyzer.analyze(
        workspace_id=WORKSPACE_ID,
        file_type_name="bank_payment_report",
        unique_column_value="RrQHFDvwIQIKiH",  # This should have both but unreconciled
        transaction_date_range=("2025-12-14", "2025-12-14")
    )
    
    if result.get("success"):
        findings = result.get("findings", [])
        scenarios = result.get("scenarios_detected", [])
        print(f"\n✅ Analysis completed")
        print(f"   Scenarios detected: {scenarios}")
        print(f"   Findings: {len(findings)}")
        print(f"   File type records: {result.get('file_type_records', {})}")
        
        scenario_c_findings = [f for f in findings if f.get("scenario") == "C"]
        print(f"\n   Scenario C findings: {len(scenario_c_findings)}")
        for i, finding in enumerate(scenario_c_findings[:2], 1):
            print(f"\n   Finding {i}:")
            print(f"      Entity ID: {finding.get('entity_id')}")
            print(f"      Issue: {finding.get('issue')}")
            print(f"      Failed Rule ID: {finding.get('failed_rule_id')}")
            if finding.get('mismatch_details'):
                print(f"      Mismatch: {list(finding.get('mismatch_details', {}).keys())}")
    else:
        print(f"❌ Analysis failed: {result.get('error')}")
    
    return result.get("success") and "C" in result.get("scenarios_detected", [])


def main():
    """Run all unified analyzer tests."""
    print("\n" + "="*70)
    print("TESTING UNIFIED ANALYZER WITH ALL THREE SCENARIOS")
    print("="*70)
    print(f"Workspace: {WORKSPACE_NAME} ({WORKSPACE_ID})")
    print(f"Using local DB: Enabled")
    
    # Load initial test data and create scenario-specific data
    print("\n🔧 Loading initial test data...")
    load_test_data()
    
    print("🔧 Creating scenario-specific test data...")
    db = get_local_db()
    try:
        create_scenario_a_data(db)
        create_scenario_b_data(db)
        create_scenario_c_data(db)
        db.conn.commit()
        print("✅ Test data created\n")
    except Exception as e:
        print(f"⚠️  Error creating test data: {e}\n")
    
    results = {
        "Scenario A": test_unified_analyzer_scenario_a(),
        "Scenario B": test_unified_analyzer_scenario_b(),
        "Scenario C": test_unified_analyzer_scenario_c(),
    }
    
    print("\n" + "="*70)
    print("UNIFIED ANALYZER TEST RESULTS SUMMARY")
    print("="*70)
    
    for scenario, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{scenario}: {status}")
    
    all_passed = all(results.values())
    print(f"\n{'✅ ALL SCENARIOS WORKING WITH UNIFIED ANALYZER!' if all_passed else '⚠️  Some scenarios need attention'}")
    print("="*70)


if __name__ == "__main__":
    main()

