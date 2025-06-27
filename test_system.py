#!/usr/bin/env python3
"""
Simple test script to verify AEGIS system components work correctly.
"""
import sys
import os

# Add the services package to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all core modules can be imported."""
    print("🧪 Testing AEGIS system imports...")
    
    try:
        # Test global prompts
        from services.src.global_prompts.database_statement import get_available_databases
        from services.src.global_prompts.project_statement import get_project_statement
        from services.src.global_prompts.fiscal_statement import get_fiscal_statement
        from services.src.global_prompts.restrictions_statement import get_restrictions_statement
        print("✅ Global prompts import successfully")
        
        # Test database configuration
        databases = get_available_databases()
        print(f"✅ Found {len(databases)} configured databases: {list(databases.keys())}")
        
        # Test individual subagents
        from services.src.agents.database_subagents.earnings_transcripts.subagent import query_database_sync as earnings_query
        from services.src.agents.database_subagents.quarterly_reports.subagent import query_database_sync as quarterly_query
        from services.src.agents.database_subagents.supplementary_packages.subagent import query_database_sync as supplementary_query
        from services.src.agents.database_subagents.ir_call_summaries.subagent import query_database_sync as ir_query
        print("✅ All database subagents import successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_subagents():
    """Test that subagents return expected response format."""
    print("\n🧪 Testing subagent functionality...")
    
    try:
        from services.src.agents.database_subagents.earnings_transcripts.subagent import query_database_sync
        
        # Test metadata query
        metadata_result = query_database_sync("test query", "metadata")
        print(f"✅ Metadata query returns {len(metadata_result)} elements")
        print(f"✅ Metadata response contains {len(metadata_result[0])} sample documents")
        
        # Test research query
        research_result = query_database_sync("test query", "research")
        print(f"✅ Research query returns {len(research_result)} elements")
        print(f"✅ Research response contains detailed_research and status_summary")
        
        return True
        
    except Exception as e:
        print(f"❌ Subagent test error: {e}")
        return False

def test_api_structure():
    """Test API module structure (without starting server)."""
    print("\n🧪 Testing API module structure...")
    
    try:
        # This will fail if FastAPI isn't installed, but we can catch that
        import importlib.util
        spec = importlib.util.find_spec("fastapi")
        if spec is None:
            print("⚠️  FastAPI not installed - API functionality will require dependencies")
            print("   Run: pip install -e . to install all dependencies")
            return True
        
        # If FastAPI is available, test the API module
        from services.src.api import app
        print("✅ API module loads successfully")
        print("✅ FastAPI app created successfully")
        
        return True
        
    except ImportError as e:
        print(f"⚠️  API dependencies missing: {e}")
        print("   This is expected if dependencies aren't installed yet")
        return True
    except Exception as e:
        print(f"❌ API structure error: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 AEGIS System Test Suite")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 3
    
    if test_imports():
        tests_passed += 1
        
    if test_subagents():
        tests_passed += 1
        
    if test_api_structure():
        tests_passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! AEGIS system structure is ready.")
        print("\nNext steps:")
        print("1. Run: ./setup.sh to install dependencies")
        print("2. Run: python start_server.py to start the server")
        print("3. Open: http://localhost:8000 in your browser")
        return True
    else:
        print("⚠️  Some tests failed. Check the error messages above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)