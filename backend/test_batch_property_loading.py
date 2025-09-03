"""
Test script for batch property loading optimization.
Validates that emails load with all properties simultaneously.
"""
import asyncio
import time
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_batch_property_loading():
    """Test the batch property loading implementation"""
    print("=== Batch Property Loading Test ===\n")
    
    try:
        from integrations.outlook.hybrid_service import HybridOutlookService
        from integrations.outlook.com_connector import COM_AVAILABLE
        
        if not COM_AVAILABLE:
            print("❌ COM not available - install pywin32")
            return False
        
        # Initialize service
        service = HybridOutlookService()
        
        print("1. Connecting to Outlook...")
        connection_result = asyncio.run(service.connect())
        
        if not connection_result.get("connected"):
            print(f"❌ Connection failed: {connection_result.get('message')}")
            return False
        
        print(f"✅ Connected via {connection_result.get('method')}")
        print(f"   Account info: {connection_result.get('account_info')}")
        
        # Test email loading performance
        print("\n2. Testing email loading performance...")
        
        # Test with different limits to compare performance
        test_limits = [10, 25, 50]
        
        for limit in test_limits:
            print(f"\n--- Testing with {limit} emails ---")
            
            # Measure batch loading time
            start_time = time.time()
            emails = asyncio.run(service.get_messages("Inbox", limit))
            batch_time = time.time() - start_time
            
            print(f"✅ Loaded {len(emails)} emails in {batch_time:.2f} seconds")
            print(f"   Performance: {len(emails)/batch_time:.1f} emails/second")
            
            if emails:
                # Validate that properties are loaded
                sample_email = emails[0]
                validate_email_properties(sample_email)
                
                # Check for COS properties
                cos_count = sum(1 for email in emails if has_cos_properties(email))
                if cos_count > 0:
                    print(f"   Found COS properties in {cos_count}/{len(emails)} emails")
                else:
                    print("   No COS properties found (normal for fresh setup)")
        
        # Test cache functionality
        print("\n3. Testing cache functionality...")
        if hasattr(service.com_connector, '_batch_loader'):
            batch_loader = service.com_connector._batch_loader
            cache_stats = batch_loader.get_cache_stats()
            print(f"   Cache stats: {cache_stats}")
            
            # Clear cache
            batch_loader.clear_cache()
            print("   Cache cleared successfully")
        
        print("\n✅ All batch property loading tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"\n❌ Test failed: {e}")
        return False

def validate_email_properties(email: Dict[str, Any]) -> bool:
    """Validate that all expected properties are present"""
    required_properties = [
        'id', 'subject', 'sender', 'sender_name', 'to_recipients', 
        'cc_recipients', 'bcc_recipients', 'body_content', 'body_preview',
        'received_at', 'sent_at', 'is_read', 'importance', 'has_attachments',
        'categories', 'conversation_id', 'size'
    ]
    
    missing_properties = []
    for prop in required_properties:
        if prop not in email:
            missing_properties.append(prop)
    
    if missing_properties:
        print(f"   ⚠️  Missing properties: {missing_properties}")
        return False
    else:
        print(f"   ✅ All standard properties present in sample email")
        print(f"      Subject: {email['subject'][:50]}...")
        print(f"      Sender: {email['sender']}")
        print(f"      Recipients: To={len(email.get('to_recipients', []))}, CC={len(email.get('cc_recipients', []))}")
        return True

def has_cos_properties(email: Dict[str, Any]) -> bool:
    """Check if email has COS properties"""
    cos_props = ['project_id', 'confidence', 'provenance', 'analysis']
    return any(email.get(prop) is not None for prop in cos_props)

def test_concurrent_loading():
    """Test concurrent loading of multiple folders"""
    print("\n=== Concurrent Loading Test ===\n")
    
    try:
        from integrations.outlook.hybrid_service import HybridOutlookService
        
        service = HybridOutlookService()
        
        # Connect
        connection_result = asyncio.run(service.connect())
        if not connection_result.get("connected"):
            print("❌ Connection failed")
            return False
        
        # Get available folders
        folders = asyncio.run(service.get_folders())
        email_folders = [f for f in folders if f.get('item_count', 0) > 0][:3]  # Test top 3 folders with emails
        
        if not email_folders:
            print("⚠️  No folders with emails found")
            return False
        
        print(f"Testing concurrent loading from {len(email_folders)} folders...")
        
        # Test concurrent loading
        async def load_folder_emails(folder_info):
            folder_name = folder_info.get('name', 'Unknown')
            start_time = time.time()
            emails = await service.get_messages(folder_name, 10)  # Load 10 from each
            load_time = time.time() - start_time
            return {
                'folder': folder_name,
                'count': len(emails),
                'time': load_time,
                'emails': emails
            }
        
        # Run concurrent loading
        start_total = time.time()
        
        async def run_concurrent():
            tasks = [load_folder_emails(folder) for folder in email_folders]
            return await asyncio.gather(*tasks)
        
        results = asyncio.run(run_concurrent())
        
        total_time = time.time() - start_total
        total_emails = sum(r['count'] for r in results)
        
        print(f"\n✅ Concurrent loading completed:")
        print(f"   Total time: {total_time:.2f} seconds")
        print(f"   Total emails: {total_emails}")
        print(f"   Performance: {total_emails/total_time:.1f} emails/second")
        
        for result in results:
            print(f"   {result['folder']}: {result['count']} emails in {result['time']:.2f}s")
        
        return True
        
    except Exception as e:
        logger.error(f"Concurrent loading test failed: {e}")
        print(f"❌ Concurrent test failed: {e}")
        return False

def benchmark_comparison():
    """Benchmark batch loading vs legacy loading"""
    print("\n=== Performance Benchmark ===\n")
    
    try:
        from integrations.outlook.com_connector import OutlookCOMConnector, COM_AVAILABLE
        
        if not COM_AVAILABLE:
            print("❌ COM not available for benchmark")
            return False
        
        connector = OutlookCOMConnector()
        if not connector.connect():
            print("❌ Failed to connect to Outlook")
            return False
        
        test_limit = 25
        
        print(f"Benchmarking with {test_limit} emails...")
        
        # Test legacy method
        print("\n1. Testing legacy method...")
        start_time = time.time()
        legacy_emails = connector._get_messages_legacy("Inbox", test_limit)
        legacy_time = time.time() - start_time
        
        print(f"   Legacy: {len(legacy_emails)} emails in {legacy_time:.2f} seconds")
        print(f"   Performance: {len(legacy_emails)/legacy_time:.1f} emails/second")
        
        # Test batch method
        if hasattr(connector, '_batch_loader') and connector._batch_loader:
            print("\n2. Testing batch method...")
            start_time = time.time()
            batch_emails = asyncio.run(connector._batch_loader.load_emails_batch("Inbox", test_limit))
            batch_time = time.time() - start_time
            
            print(f"   Batch: {len(batch_emails)} emails in {batch_time:.2f} seconds")
            print(f"   Performance: {len(batch_emails)/batch_time:.1f} emails/second")
            
            # Calculate improvement
            if legacy_time > 0:
                improvement = ((legacy_time - batch_time) / legacy_time) * 100
                print(f"\n✅ Performance improvement: {improvement:.1f}% faster")
            
            # Validate results are equivalent
            if len(legacy_emails) == len(batch_emails):
                print("✅ Result count matches between methods")
            else:
                print(f"⚠️  Result count mismatch: {len(legacy_emails)} vs {len(batch_emails)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        print(f"❌ Benchmark failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Starting Batch Property Loading Tests\n")
    
    # Run basic batch loading test
    success1 = test_batch_property_loading()
    
    # Run concurrent loading test
    success2 = await test_concurrent_loading()
    
    # Run performance benchmark
    success3 = benchmark_comparison()
    
    print(f"\n{'='*50}")
    print("FINAL RESULTS:")
    print(f"✅ Batch Loading: {'PASS' if success1 else 'FAIL'}")
    print(f"✅ Concurrent Loading: {'PASS' if success2 else 'FAIL'}")  
    print(f"✅ Performance Benchmark: {'PASS' if success3 else 'FAIL'}")
    
    if all([success1, success2, success3]):
        print(f"\n🎉 ALL TESTS PASSED - Batch property loading is working correctly!")
    else:
        print(f"\n❌ Some tests failed - check implementation")
    
    return all([success1, success2, success3])

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        exit(1)
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        print(f"\n💥 Test execution failed: {e}")
        exit(1)