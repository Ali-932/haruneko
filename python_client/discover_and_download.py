#!/usr/bin/env python3
"""
Discovery and Download Script - Learn how to find manga and download chapters

This script shows the REAL workflow for using the HaruNeko API:
1. Search for manga
2. Inspect the manga IDs returned
3. Get chapters for a manga
4. Download specific chapters

⚠️  IMPORTANT: Start the HaruNeko API server first!
    cd .. && npm run dev
"""

import json
import sys
from haruneko_download_service import HaruNekoDownloadService


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def discover_manga(service, source_id, search_query):
    """
    Step 1: Search for manga and discover the ID format for this source
    """
    print_section(f"STEP 1: Searching for '{search_query}' on {source_id}")

    try:
        results = service.search_manga(source_id, search_query, page=1, limit=10)

        if not results:
            print(f"❌ No results found for '{search_query}' on {source_id}")
            return None

        print(f"✓ Found {len(results)} results!\n")

        # Show first 3 results
        for i, manga in enumerate(results[:3], 1):
            print(f"{i}. {manga.get('title', 'Unknown Title')}")
            print(f"   ID: {manga['id'][:80]}...")  # Truncate long IDs
            print(f"   Source: {manga.get('sourceId', 'N/A')}")
            print()

        # Let user pick
        if len(results) == 1:
            choice = 1
        else:
            try:
                choice = int(input(f"Select manga (1-{min(3, len(results))}): "))
                if choice < 1 or choice > min(3, len(results)):
                    choice = 1
            except (ValueError, EOFError):
                choice = 1
                print(f"Using default: {choice}")

        selected = results[choice - 1]
        print(f"\n✓ Selected: {selected.get('title', 'Unknown')}")
        print(f"  Full Manga ID: {selected['id']}")

        return selected

    except Exception as e:
        print(f"❌ Error searching: {e}")
        return None


def discover_chapters(service, source_id, manga):
    """
    Step 2: Get chapters and discover the ID format for chapters
    """
    print_section("STEP 2: Fetching Chapters")

    manga_id = manga['id']
    manga_title = manga.get('title', 'Unknown')

    print(f"Manga: {manga_title}")
    print(f"Manga ID: {manga_id}\n")

    try:
        chapters = service.fetch_chapters(source_id, manga_id)

        if not chapters:
            print("❌ No chapters found!")
            return None

        print(f"✓ Found {len(chapters)} chapters!\n")

        # Show first 5 chapters
        print("First 5 chapters:")
        for i, chapter in enumerate(chapters[:5], 1):
            print(f"{i}. {chapter.get('title', 'Unknown Chapter')}")
            print(f"   Chapter ID: {chapter['id']}")
            if chapter.get('number'):
                print(f"   Number: {chapter['number']}")
            print()

        return chapters

    except Exception as e:
        print(f"❌ Error fetching chapters: {e}")
        return None


def download_chapters(service, source_id, manga, chapters, num_chapters=2):
    """
    Step 3: Download specific chapters
    """
    print_section(f"STEP 3: Downloading {num_chapters} Chapters")

    if len(chapters) < num_chapters:
        num_chapters = len(chapters)

    chapter_ids = [ch['id'] for ch in chapters[:num_chapters]]
    manga_id = manga['id']

    print(f"Manga: {manga.get('title', 'Unknown')}")
    print(f"Downloading {num_chapters} chapters:")
    for i, ch in enumerate(chapters[:num_chapters], 1):
        print(f"  {i}. {ch.get('title', 'Unknown')}")
    print()

    try:
        result = service.download_chapters(
            source_id=source_id,
            manga_id_raw=manga_id,
            chapter_ids=chapter_ids,
            format="cbz",
            options={"quality": "high", "includeMetadata": True}
        )

        if result['success']:
            print("✓ Download request successful!")
            download_data = result['response'].get('data', {})
            download_id = download_data.get('id', 'N/A')
            status = download_data.get('status', 'unknown')

            print(f"  Download ID: {download_id}")
            print(f"  Status: {status}")
            print(f"\n📊 To check download progress:")
            print(f"  GET http://localhost:3000/api/v1/downloads/{download_id}")
            print(f"\n📦 To get the file (when completed):")
            print(f"  GET http://localhost:3000/api/v1/downloads/{download_id}/file")
        else:
            print(f"❌ Download failed: {result['error']}")

    except Exception as e:
        print(f"❌ Error downloading: {e}")


def main():
    """Main interactive workflow"""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║              HaruNeko API - Discovery & Download Tool            ║
╚══════════════════════════════════════════════════════════════════╝

This script helps you discover manga and chapter IDs, then download them.

⚠️  CRITICAL: Make sure the HaruNeko API server is running!

   In another terminal, run:
   $ cd /path/to/haruneko
   $ npm run dev

   Then verify at: http://localhost:3000/api-docs
""")

    input("Press Enter when the API server is ready...")

    # Initialize service
    service = HaruNekoDownloadService(
        base_url="http://localhost:3000/api/v1"
    )

    # Configuration
    print("\nEnter search details (or press Enter for defaults):")
    source_id = input("Source ID [mangadex]: ").strip() or "mangadex"
    search_query = input("Search query [one piece]: ").strip() or "one piece"

    # Step 1: Discover manga
    manga = discover_manga(service, source_id, search_query)
    if not manga:
        print("\n❌ Could not find manga. Exiting.")
        sys.exit(1)

    # Step 2: Discover chapters
    chapters = discover_chapters(service, source_id, manga)
    if not chapters:
        print("\n❌ Could not get chapters. Exiting.")
        sys.exit(1)

    # Step 3: Download
    download_choice = input(f"\nDownload first 2 chapters? [y/N]: ").strip().lower()
    if download_choice == 'y':
        download_chapters(service, source_id, manga, chapters, num_chapters=2)
    else:
        print("\n✓ Skipping download. You now know the manga and chapter IDs!")
        print(f"  Manga ID: {manga['id']}")
        print(f"  Chapter IDs: {[ch['id'] for ch in chapters[:3]]}")

    print_section("WORKFLOW COMPLETE!")
    print("""
What you learned:
1. How to search for manga and get the manga ID format for your source
2. How to fetch chapters and get the chapter ID format
3. How to initiate downloads and track them

Next steps:
- Use these IDs in your own scripts
- Check download status via the API
- Download the completed files when ready
""")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
