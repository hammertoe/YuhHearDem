#!/usr/bin/env python3
"""Test the API endpoints"""

import asyncio
import signal
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_api():
    """Test API endpoints"""

    import httpx

    print("=" * 60)
    print("YuhHearDem API Test")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Root endpoint
        print("\n[1] Testing root endpoint...")
        try:
            r1 = await client.get("http://127.0.0.1:8000/")
            print(f"    Status: {r1.status_code}")
            print(f"    Response: {r1.json()}")
        except Exception as e:
            print(f"    FAILED: {e}")

        # Test 2: Health endpoint
        print("\n[2] Testing health endpoint...")
        try:
            r2 = await client.get("http://127.0.0.1:8000/health")
            print(f"    Status: {r2.status_code}")
            print(f"    Response: {r2.json()}")
        except Exception as e:
            print(f"    FAILED: {e}")

        # Test 3: List videos
        print("\n[3] Testing /api/videos endpoint...")
        try:
            r3 = await client.get("http://127.0.0.1:8000/api/videos")
            print(f"    Status: {r3.status_code}")
            data = r3.json()
            print(f"    Videos found: {len(data)}")
        except Exception as e:
            print(f"    FAILED: {e}")

        # Test 4: Chat endpoint
        print("\n[4] Testing chat endpoint...")
        try:
            r4 = await client.post(
                "http://127.0.0.1:8000/api/chat",
                json={"query": "test query", "session_id": None},
            )
            print(f"    Status: {r4.status_code}")
            print(f"    Response preview: {r4.text[:200]}...")
        except Exception as e:
            print(f"    FAILED: {e}")

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)


def start_server():
    """Start the API server"""
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


async def main():
    """Main test function"""

    print("Starting API server...")

    # Start server
    server = start_server()

    # Wait for server to start
    print("Waiting for server to start (5 seconds)...")
    await asyncio.sleep(5)

    # Run tests
    try:
        await test_api()
    except Exception as e:
        print(f"Test failed: {e}")

    # Shutdown server
    print("\nShutting down server...")
    server.terminate()
    server.wait()

    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
