"""
Simple test script to verify AI re-processing functionality.
"""
import asyncio
import logging
import sys
from datetime import datetime

# Add backend to path
sys.path.append('.')

from email_intelligence import EmailIntelligenceService
from claude_client import ClaudeClient

# Setup logging
logging.basicConfig(level=logging.DEBUG)

async def test_ai_processing():
    """Test the AI email processing functionality"""
    print("=" * 50)
    print("TESTING AI RE-PROCESSING FUNCTIONALITY")
    print("=" * 50)
    
    try:
        # Initialize Claude client
        print("Initializing Claude client...")
        claude_client = ClaudeClient()
        print("Claude client initialized")
        
        # Initialize email intelligence service
        print("Initializing Email Intelligence Service...")
        intelligence_service = EmailIntelligenceService(claude_client)
        print("Email Intelligence Service initialized")
        
        # Create test email data
        test_email = {
            "subject": "Urgent: Budget Review Meeting - Action Required",
            "sender_name": "Sarah Johnson (CEO)",
            "body_content": "Need to schedule Q4 budget review meeting. Please confirm availability for Tuesday 2-4 PM or Wednesday 10 AM-12 PM. Critical for year-end planning.",
            "preview": "Need to schedule Q4 budget review meeting..."
        }
        
        print("Created test email:", test_email['subject'][:50])
        
        # Get initial stats
        print("Getting initial usage statistics...")
        try:
            initial_stats = await claude_client.get_usage_statistics()
            initial_calls = initial_stats.get('api_calls', 0)
            initial_cost = initial_stats.get('estimated_cost', 0.0)
            print("Initial stats: calls={}, cost=${:.4f}".format(initial_calls, initial_cost))
        except Exception as stats_error:
            print("Could not get initial stats:", stats_error)
            initial_calls = 0
            initial_cost = 0.0
        
        # Perform AI analysis
        print("Starting AI analysis...")
        start_time = datetime.now()
        
        analysis_result = await intelligence_service.analyze_email(test_email)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        print("Analysis completed in {:.2f} seconds".format(processing_time))
        
        # Check analysis results
        if analysis_result and isinstance(analysis_result, dict):
            print("Analysis result received:")
            print("  Priority:", analysis_result.get('priority', 'Unknown'))
            print("  Tone:", analysis_result.get('tone', 'Unknown'))
            print("  Urgency:", analysis_result.get('urgency', 'Unknown'))
            print("  Summary:", analysis_result.get('summary', 'No summary')[:100])
            print("  Confidence:", analysis_result.get('confidence', 0))
            print("  Action Required:", analysis_result.get('action_required', False))
        else:
            print("No valid analysis result received")
            return False
        
        # Get final stats
        print("Getting final usage statistics...")
        try:
            final_stats = await claude_client.get_usage_statistics()
            final_calls = final_stats.get('api_calls', 0)
            final_cost = final_stats.get('estimated_cost', 0.0)
            print("Final stats: calls={}, cost=${:.4f}".format(final_calls, final_cost))
        except Exception as stats_error:
            print("Could not get final stats:", stats_error)
            final_calls = initial_calls
            final_cost = initial_cost
        
        # Calculate changes
        calls_increase = final_calls - initial_calls
        cost_increase = final_cost - initial_cost
        
        print("Changes: +{} API calls, +${:.4f} cost".format(calls_increase, cost_increase))
        
        # Evaluate results
        print("=" * 50)
        print("EVALUATION RESULTS:")
        print("=" * 50)
        
        real_api_call = calls_increase > 0
        cost_increased = cost_increase > 0
        reasonable_timing = 1.0 <= processing_time <= 30.0
        quality_analysis = analysis_result and analysis_result.get('confidence', 0) > 0.5
        
        print("Real API call made:", real_api_call, "(calls increased by {})".format(calls_increase))
        print("Cost tracking working:", cost_increased, "(cost increased by ${:.4f})".format(cost_increase))
        print("Reasonable timing:", reasonable_timing, "({:.2f}s)".format(processing_time))
        print("Quality analysis:", quality_analysis, "(confidence: {})".format(analysis_result.get('confidence', 0)))
        
        overall_success = real_api_call and reasonable_timing and quality_analysis
        
        if overall_success:
            print("\nSUCCESS: AI re-processing is working correctly!")
            print("• Claude API is being called")
            print("• Processing time indicates real AI analysis")
            print("• Analysis quality suggests genuine Claude responses")
        else:
            print("\nISSUES DETECTED:")
            if not real_api_call:
                print("• No API calls made - might be using cached/fallback responses")
            if not reasonable_timing:
                print("• Unusual timing - too fast might indicate caching")
            if not quality_analysis:
                print("• Low quality analysis - might be fallback responses")
        
        return overall_success
        
    except Exception as e:
        print("Test failed with error:", e)
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_ai_processing())
    sys.exit(0 if success else 1)