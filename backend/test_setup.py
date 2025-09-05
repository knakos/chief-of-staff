"""
Test script to verify the Chief of Staff backend setup.
This is a wrapper that calls the comprehensive system test.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

async def test_setup():
    """Run comprehensive system tests"""
    from test_system import run_all_tests
    return await run_all_tests()

if __name__ == "__main__":
    try:
        success = asyncio.run(test_setup())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Test setup failed: {e}")
        sys.exit(1)