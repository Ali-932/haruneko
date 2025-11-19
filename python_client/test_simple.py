#!/usr/bin/env python3
"""
Test Script - Simplified API Testing

This script tests the simplified download_manga_chapters() API.

Prerequisites:
    1. Start HaruNeko API: cd .. && npm run dev
    2. Run this script: python test_simple.py
"""

import time
import requests
from haruneko_download_service import HaruNekoDownloadService


def poll_download_status(download_id: str, base_url: str = "http://localhost:3000/api/v1", timeout: int = 300):
    """
    Poll download status until completed or failed

    Args:
        download_id: The download ID to poll
        base_url: API base URL
        timeout: Maximum time to wait in seconds

    Returns:
        Final status dict
    """
    start_time = time.time()

    while True:
        # Check if timeout exceeded
        if time.time() - start_time > timeout:
            print(f"\n⏱️  Timeout after {timeout}s")
            return None

        # Get download status
        response = requests.get(f"{base_url}/downloads/{download_id}")
        data = response.json()

        if not data.get("success"):
            print(f"\n❌ Error getting status: {data.get('error')}")
            return None

        status_info = data["data"]
        status = status_info["status"]
        progress = status_info.get("progress", 0)

        # Print status update
        print(f"\r  Status: {status.ljust(15)} Progress: {progress:.1f}%", end="", flush=True)

        # Check if complete
        if status == "completed":
            print()  # New line
            return status_info
        elif status == "failed":
            print()
            error = status_info.get("error", "Unknown error")
            print(f"\n❌ Download failed: {error}")
            return status_info
        elif status == "cancelled":
            print()
            print(f"\n⚠️  Download was cancelled")
            return status_info

        # Wait before next poll
        time.sleep(2)


def test_validate_only():
    """Test validation without downloading"""
    print("\n" + "="*70)
    print("TEST 1: Validate manga and chapters")
    print("="*70)

    service = HaruNekoDownloadService()

    result = service.download_manga_chapters(
        source_id="mangahere",
        manga_name="One Piece",
        chapter_numbers=[1, 2, 3],
        validate_only=True
    )

    print("\nResult:")
    print(f"  Success: {result['success']}")
    if result['success']:
        print(f"  Manga: {result['manga']['title']}")
        print(f"  Chapters matched: {len(result['chapters_found'])}")
        for ch in result['chapters_found']:
            print(f"    - {ch.get('title', 'Unknown')}")
    else:
        print(f"  Error: {result['error']}")

    return result


def test_missing_chapters():
    """Test with chapters that don't exist"""
    print("\n" + "="*70)
    print("TEST 2: Request non-existent chapters")
    print("="*70)

    service = HaruNekoDownloadService()

    result = service.download_manga_chapters(
        source_id="mangahere",
        manga_name="One Piece",
        chapter_numbers=[99999, 99998],  # These probably don't exist
        validate_only=True
    )

    print("\nResult:")
    print(f"  Success: {result['success']}")
    print(f"  Error: {result.get('error', 'None')}")
    print(f"  Missing: {result['chapters_missing']}")

    return result


def test_download():
    """Test actual download with status polling"""
    print("\n" + "="*70)
    print("TEST 3: Download chapter with status polling")
    print("="*70)
    print("⚠️  This test is commented out to avoid actual downloads")
    print("⚠️  Note: mangahere may have Puppeteer issues - try another source if it fails")
    print("Uncomment the code below to test downloading\n")

    # Uncomment to test actual download:
    # service = HaruNekoDownloadService()
    #
    # # Initiate download
    # result = service.download_manga_chapters(
    #     source_id="mangahere",
    #     manga_name="One Piece",
    #     chapter_numbers=[1],
    #     format="cbz"
    # )
    #
    # if not result['success']:
    #     print(f"\n✗ Failed to initiate download: {result['error']}")
    #     return
    #
    # download_id = result['download']['response']['data']['id']
    # print(f"\n✓ Download initiated! ID: {download_id}")
    # print(f"\nPolling for completion (this may take a while)...")
    #
    # # Poll for completion
    # final_status = poll_download_status(download_id)
    #
    # if final_status and final_status['status'] == 'completed':
    #     file_url = final_status.get('fileUrl')
    #     print(f"\n✓ Download complete!")
    #     print(f"  File URL: {file_url}")
    #     print(f"\nDownload the file:")
    #     print(f"  curl http://localhost:3000{file_url} -o manga.cbz")
    # else:
    #     print(f"\n✗ Download did not complete successfully")


def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║         HaruNeko API - Simplified API Test Suite                ║
╚══════════════════════════════════════════════════════════════════╝

This tests the new simplified API that only needs:
  - source_id (e.g., "mangahere")
  - manga_name (e.g., "One Piece")
  - chapter_numbers (e.g., [1, 2, 3])

Note: Downloads are ASYNC! The API:
  1. Returns a download ID immediately
  2. Processes download in background
  3. You poll /api/v1/downloads/{id} for status
  4. When completed, download file from /api/v1/downloads/{id}/file
""")

    try:
        # Test 1: Validate manga and chapters
        test_validate_only()

        # Test 2: Non-existent chapters
        test_missing_chapters()

        # Test 3: Download with polling (commented out)
        test_download()

        print("\n" + "="*70)
        print("Tests complete!")
        print("="*70)

    except ConnectionError:
        print("\n❌ ERROR: Cannot connect to API!")
        print("\nMake sure the server is running:")
        print("  $ cd .. && npm run dev")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
