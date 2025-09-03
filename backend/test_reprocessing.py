"""
Test script to verify that re-processing requests now generate new analysis.
This script tests the force_reanalysis functionality.
"""
import asyncio
import logging
import sys
from datetime import datetime

# Add backend to path
sys.path.append('.')

from integrations.outlook.com_service import OutlookCOMService
from email_intelligence import EmailIntelligenceService
from claude_client import ClaudeClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_reprocessing():
    """Test that re-processing generates new analysis each time"""
    print("=" * 60)
    print("TESTING RE-PROCESSING WITH FORCE REANALYSIS")
    print("=" * 60)
    
    try:
        # Initialize services
        print("[INIT] Initializing services...")
        claude_client = ClaudeClient()
        intelligence_service = EmailIntelligenceService(claude_client)
        com_service = OutlookCOMService()
        
        # Inject intelligence service
        com_service.intelligence_service = intelligence_service
        
        # Connect to Outlook
        connection_result = com_service.connect()
        if not connection_result.get('connected'):
            print(f"[ERROR] Failed to connect to Outlook COM: {connection_result.get('message')}")
            return False
        
        print("[OK] Services initialized and connected")
        
        # Get a sample email ID (we'll use the first email from inbox)
        print("[SEARCH] Getting sample email from inbox...")
        emails = com_service.get_recent_emails("Inbox", limit=1)
        
        if not emails:
            print("[ERROR] No emails found in inbox for testing")
            return False
        
        email_id = emails[0].get('id')
        subject = emails[0].get('subject', 'Unknown')[:50]
        print(f"[EMAIL] Using email: '{subject}' (ID: {email_id})")
        
        # Get initial usage stats
        initial_stats = await claude_client.get_usage_statistics()
        initial_calls = initial_stats.get('api_calls', 0)
        initial_cost = initial_stats.get('estimated_cost', 0.0)
        print(f"[STATS] Initial API stats: calls={initial_calls}, cost=${initial_cost:.4f}")
        
        # First analysis (should generate new analysis)
        print("\n[ANALYSIS1] FIRST ANALYSIS (force_reanalysis=True by default)...")
        start_time = datetime.now()
        
        first_result = await com_service.analyze_single_email(email_id)
        
        end_time = datetime.now()
        first_time = (end_time - start_time).total_seconds()
        
        # Check stats after first call
        mid_stats = await claude_client.get_usage_statistics()
        mid_calls = mid_stats.get('api_calls', 0)
        mid_cost = mid_stats.get('estimated_cost', 0.0)
        
        first_calls_increase = mid_calls - initial_calls
        first_cost_increase = mid_cost - initial_cost
        
        print(f"[TIME] First analysis took: {first_time:.2f} seconds")
        print(f"[IMPACT] First analysis API impact: +{first_calls_increase} calls, +${first_cost_increase:.4f} cost")
        
        if first_result and first_result.get('analysis'):
            first_analysis = first_result['analysis']
            print(f"[OK] First analysis: priority={first_analysis.get('priority')}, confidence={first_analysis.get('confidence')}")
        else:
            print("[ERROR] First analysis failed or returned no result")
            return False
        
        # Wait a moment to ensure different timestamps
        await asyncio.sleep(2)
        
        # Second analysis (should generate ANOTHER new analysis due to force_reanalysis=True)
        print("\n[ANALYSIS2] SECOND ANALYSIS (force_reanalysis=True by default)...")
        start_time = datetime.now()
        
        second_result = await com_service.analyze_single_email(email_id)
        
        end_time = datetime.now()
        second_time = (end_time - start_time).total_seconds()
        
        # Check final stats
        final_stats = await claude_client.get_usage_statistics()
        final_calls = final_stats.get('api_calls', 0)
        final_cost = final_stats.get('estimated_cost', 0.0)
        
        second_calls_increase = final_calls - mid_calls
        second_cost_increase = final_cost - mid_cost
        
        print(f"[TIME] Second analysis took: {second_time:.2f} seconds")
        print(f"[IMPACT] Second analysis API impact: +{second_calls_increase} calls, +${second_cost_increase:.4f} cost")
        
        if second_result and second_result.get('analysis'):
            second_analysis = second_result['analysis']
            print(f"[OK] Second analysis: priority={second_analysis.get('priority')}, confidence={second_analysis.get('confidence')}")
        else:
            print("[ERROR] Second analysis failed or returned no result")
            return False
        
        # Evaluation
        print("\n" + "=" * 60)
        print("REPROCESSING EVALUATION:")
        print("=" * 60)
        
        both_made_api_calls = first_calls_increase > 0 and second_calls_increase > 0
        both_had_realistic_timing = first_time > 2.0 and second_time > 2.0
        both_increased_cost = first_cost_increase > 0 and second_cost_increase > 0
        total_calls_increase = final_calls - initial_calls
        total_cost_increase = final_cost - initial_cost
        
        print(f"[CHECK] First analysis made API call: {first_calls_increase > 0} (+{first_calls_increase} calls)")
        print(f"[CHECK] Second analysis made API call: {second_calls_increase > 0} (+{second_calls_increase} calls)")
        print(f"[CHECK] Both had realistic timing: {both_had_realistic_timing} ({first_time:.1f}s, {second_time:.1f}s)")
        print(f"[CHECK] Both increased cost: {both_increased_cost} (+${first_cost_increase:.4f}, +${second_cost_increase:.4f})")
        print(f"[TOTAL] Total impact: +{total_calls_increase} API calls, +${total_cost_increase:.4f} cost")
        
        success = both_made_api_calls and both_had_realistic_timing and both_increased_cost
        
        if success:
            print("\n[SUCCESS] Re-processing is now working correctly!")
            print("   * Each re-processing request generates fresh analysis")
            print("   * Force reanalysis bypasses existing analysis cache")
            print("   * Claude API is called for every re-processing request")
            print("   * Cost tracking works properly for each call")
        else:
            print("\n[ISSUES] ISSUES STILL DETECTED:")
            if not both_made_api_calls:
                print("   * One or both analyses didn't make API calls")
            if not both_had_realistic_timing:
                print("   * Timing too fast - might indicate cached responses")
            if not both_increased_cost:
                print("   * Cost didn't increase for both calls")
        
        return success
        
    except Exception as e:
        print(f"[ERROR] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_reprocessing())
    sys.exit(0 if success else 1)