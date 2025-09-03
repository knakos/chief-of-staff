"""
Test script to verify AI re-processing functionality.
This script simulates the frontend's email analysis request to verify that:
1. Claude API is actually being called
2. Costs are being tracked
3. Real analysis is performed (not cached/fallback results)
"""
import asyncio
import logging
import sys
import json
from datetime import datetime

# Add backend to path
sys.path.append('.')

from email_intelligence import EmailIntelligenceService
from claude_client import ClaudeClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_ai_processing():
    """Test the AI email processing functionality"""
    print("="*60)
    print("TESTING AI RE-PROCESSING FUNCTIONALITY")
    print("="*60)
    
    try:
        # Initialize Claude client
        print("[API] Initializing Claude client...")
        claude_client = ClaudeClient()
        
        # Check if API key is configured
        if not hasattr(claude_client, 'client') or not claude_client.client:
            print("[ERROR] Claude API client not properly configured. Check ANTHROPIC_API_KEY in .env")
            return False
            
        print("[OK] Claude client initialized successfully")
        
        # Initialize email intelligence service
        print("[AI] Initializing Email Intelligence Service...")
        intelligence_service = EmailIntelligenceService(claude_client)
        print("[OK] Email Intelligence Service initialized")
        
        # Create test email data
        test_email = {
            "id": "test_email_001",
            "subject": "Urgent: Q4 Budget Review Meeting - Action Required",
            "sender_name": "Sarah Johnson (CEO)",
            "sender": "sarah.johnson@company.com",
            "body_content": """Hi Team,

I need to schedule our Q4 budget review meeting for next week. This is critical for our year-end planning and we need to ensure all department heads are present.

Please confirm your availability for:
- Tuesday, October 15th, 2:00 PM - 4:00 PM
- Wednesday, October 16th, 10:00 AM - 12:00 PM

We'll be reviewing budget allocations, performance metrics, and planning for Q1 2025. Please bring your department's financial reports and projected needs.

Time is of the essence here - we need to finalize everything before the board meeting on October 20th.

Thanks,
Sarah

Sarah Johnson
Chief Executive Officer
Company Inc.
Phone: (555) 123-4567
Email: sarah.johnson@company.com
""",
            "received_at": datetime.now().isoformat(),
            "preview": "I need to schedule our Q4 budget review meeting for next week..."
        }
        
        print(f"📧 Created test email: '{test_email['subject'][:50]}...'")
        
        # Track initial state
        print("📊 Getting initial usage statistics...")
        initial_stats = await claude_client.get_usage_statistics()
        print(f"📊 Initial stats: API calls={initial_stats.get('api_calls', 0)}, Cost=${initial_stats.get('estimated_cost', 0.0):.4f}")
        
        # Perform AI analysis
        print("\n🔄 Starting AI analysis...")
        print("⏱️  This should take several seconds if actually calling Claude API...")
        
        start_time = datetime.now()
        
        try:
            analysis_result = await intelligence_service.analyze_email(test_email)
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            print(f"⏱️  Analysis completed in {processing_time:.2f} seconds")
            
            # Check if we got real analysis results
            if analysis_result and isinstance(analysis_result, dict):
                print("✅ Analysis result received:")
                print(f"   🎯 Priority: {analysis_result.get('priority', 'Unknown')}")
                print(f"   🎭 Tone: {analysis_result.get('tone', 'Unknown')}")
                print(f"   ⚡ Urgency: {analysis_result.get('urgency', 'Unknown')}")
                print(f"   📋 Summary: {analysis_result.get('summary', 'No summary')[:100]}...")
                print(f"   🎪 Confidence: {analysis_result.get('confidence', 0)}")
                print(f"   🔧 Action Required: {analysis_result.get('action_required', False)}")
                
                # Check for quality indicators of real AI analysis
                has_detailed_summary = analysis_result.get('summary', '') and len(analysis_result.get('summary', '')) > 50
                has_suggested_actions = analysis_result.get('suggested_actions', []) and len(analysis_result.get('suggested_actions', [])) > 0
                has_reasoning = analysis_result.get('reasoning', '') and len(analysis_result.get('reasoning', '')) > 20
                
                quality_score = sum([has_detailed_summary, has_suggested_actions, has_reasoning])
                print(f"   📈 Analysis quality score: {quality_score}/3 (detailed summary: {has_detailed_summary}, actions: {has_suggested_actions}, reasoning: {has_reasoning})")
                
            else:
                print("❌ No valid analysis result received")
                return False
                
        except Exception as analysis_error:
            print(f"❌ Analysis failed: {analysis_error}")
            return False
        
        # Check final usage statistics
        print("\n📊 Getting final usage statistics...")
        final_stats = await claude_client.get_usage_statistics()
        print(f"📊 Final stats: API calls={final_stats.get('api_calls', 0)}, Cost=${final_stats.get('estimated_cost', 0.0):.4f}")
        
        # Calculate changes
        api_calls_increase = final_stats.get('api_calls', 0) - initial_stats.get('api_calls', 0)
        cost_increase = final_stats.get('estimated_cost', 0.0) - initial_stats.get('estimated_cost', 0.0)
        
        print(f"📈 Changes: +{api_calls_increase} API calls, +${cost_increase:.4f} cost")
        
        # Evaluate results
        print("\n" + "="*60)
        print("🎯 EVALUATION RESULTS:")
        print("="*60)
        
        real_api_call = api_calls_increase > 0
        cost_increased = cost_increase > 0
        reasonable_timing = 2.0 <= processing_time <= 15.0  # Real API calls should take 2-15 seconds
        quality_analysis = analysis_result and analysis_result.get('confidence', 0) > 0.7
        
        print(f"✅ Real API call made: {real_api_call} (calls increased by {api_calls_increase})")
        print(f"✅ Cost tracking working: {cost_increased} (cost increased by ${cost_increase:.4f})")
        print(f"✅ Reasonable timing: {reasonable_timing} ({processing_time:.2f}s - real API calls take 2-15s)")
        print(f"✅ Quality analysis: {quality_analysis} (confidence: {analysis_result.get('confidence', 0)})")
        
        overall_success = real_api_call and cost_increased and reasonable_timing and quality_analysis
        
        if overall_success:
            print("\n🎉 SUCCESS: AI re-processing is working correctly!")
            print("   • Claude API is being called")
            print("   • Costs are being tracked properly") 
            print("   • Processing time indicates real AI analysis")
            print("   • Analysis quality suggests genuine Claude responses")
        else:
            print("\n⚠️  ISSUES DETECTED:")
            if not real_api_call:
                print("   • No API calls made - might be using cached/fallback responses")
            if not cost_increased:
                print("   • No cost increase - API might not be called")
            if not reasonable_timing:
                print("   • Unusual timing - too fast might indicate caching, too slow might indicate issues")
            if not quality_analysis:
                print("   • Low quality analysis - might be fallback/default responses")
        
        return overall_success
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_ai_processing())
    sys.exit(0 if success else 1)