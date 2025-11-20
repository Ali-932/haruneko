#!/usr/bin/env python3
"""
Simple Example - Download manga chapters with minimal code

Usage:
    1. Start the HaruNeko API: cd .. && npm run dev
    2. Run this script: python simple_example.py
"""

import time
import requests
from haruneko_download_service import HaruNekoDownloadService


def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║              HaruNeko API - Simple Example                       ║
╚══════════════════════════════════════════════════════════════════╝
""")

    # Initialize service
    service = HaruNekoDownloadService()

    # Example 1: Validate only (check if manga and chapters exist)
    print("\n" + "="*70)
    print("EXAMPLE 1: Validate manga and chapters (dry run)")
    print("="*70)

    result = service.download_manga_chapters(
        source_id="mangahere",
        manga_name="One Piece",
        chapter_numbers=[1, 2, 3],
        validate_only=True  # Just check, don't download
    )

    if result["success"]:
        print("\n✓ Validation successful!")
        print(f"  Manga: {result['manga']['title']}")
        print(f"  Chapters found: {len(result['chapters_found'])}")
    else:
        print(f"\n✗ Validation failed: {result['error']}")

    # Example 2: Download with status polling (commented out)
    print("\n" + "="*70)
    print("EXAMPLE 2: Download chapters with polling (uncomment to use)")
    print("="*70)
    print("⚠️  Downloads are ASYNC - they process in the background!")
    print("To actually download, uncomment the code below in this script\n")

    # Uncomment to download:
    # # Step 1: Initiate download
    result = service.download_manga_chapters(
        source_id="mangahere",
        manga_name="One Piece",
        chapter_numbers=[1, 2, 3],  # Start with just 1 chapter
        format="images",
        options={"quality": "high", "includeMetadata": True}
    )

    if not result["success"]:
        print(f"\n✗ Download failed: {result['error']}")
        return

    download_id = result["download"]["response"]["data"]["id"]
    print(f"\n✓ Download initiated! ID: {download_id}")
    print(f"⏳ Waiting for download to complete (polling every 2s)...\n")

    # Step 2: Poll for completion
    base_url = "http://localhost:3000/api/v1"
    start_time = time.time()
    timeout = 300  # 5 minutes

    while True:
        # Check timeout
        if time.time() - start_time > timeout:
            print(f"\n⏱️  Timeout after {timeout}s")
            break

        # Get status
        response = requests.get(f"{base_url}/downloads/{download_id}")
        data = response.json()

        if not data.get("success"):
            print(f"\n❌ Error: {data.get('error')}")
            break

        status_info = data["data"]
        status = status_info["status"]
        progress = status_info.get("progress", 0)

        # Print status
        print(f"\r  Status: {status.ljust(15)} Progress: {progress:.1f}%", end="", flush=True)

        # Check if done
        if status == "completed":
            file_url = status_info.get("fileUrl")
            print(f"\n\n✓ Download complete!")
            print(f"  File URL: {file_url}")
            print(f"\nDownload the file:")
            print(f"  curl http://localhost:3000{file_url} -o manga.cbz")
            break
        elif status == "failed":
            error = status_info.get("error", "Unknown error")
            print(f"\n\n❌ Download failed: {error}")
            break

        # Wait before next poll
        time.sleep(2)

    print("\n" + "="*70)
    print("Done! See test_simple.py for more examples")
    print("="*70)


if __name__ == "__main__":
    try:
        main()
    except ConnectionError:
        print("\n❌ ERROR: Cannot connect to API server!")
        print("\nStart the server first:")
        print("  $ cd .. && npm run dev")
        print("\nThen run this script again.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
