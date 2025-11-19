#!/usr/bin/env python3
"""
Test script for HaruNeko Download Service

This script demonstrates how to:
1. Search for a manga
2. Validate that specific chapters exist
3. Download chapters

Usage:
    python test_client.py

Requirements:
    pip install requests
"""

import json
from haruneko_download_service import HaruNekoDownloadService


def test_berserk_example():
    """
    Example: Download Berserk chapters from mangahere
    """
    # Initialize service
    service = HaruNekoDownloadService(
        base_url="http://localhost:3000/api/v1",
        download_root="downloads"
    )

    # Manga information
    source_id = "mangahere"
    manga_title = "berserk"
    post = "4737"
    slug = "/manga/berserk/"

    # Chapters to download (you need to provide valid chapter IDs)
    # Example format: "/manga/berserk/c001/"
    chapter_ids = [
        "/manga/berserk/c001/",
        "/manga/berserk/c002/",
        "/manga/berserk/c003/",
    ]

    # Option 1: Validate only (dry-run)
    print("\n" + "="*60)
    print("TEST 1: Validation Only (Dry Run)")
    print("="*60)

    result = service.validate_and_download(
        source_id=source_id,
        manga_title=manga_title,
        post=post,
        slug=slug,
        chapter_ids=chapter_ids,
        validate_only=True  # Only validate, don't download
    )

    print(f"\nValidation Result:")
    print(json.dumps(result, indent=2))

    # Option 2: Validate AND download
    print("\n" + "="*60)
    print("TEST 2: Validate and Download")
    print("="*60)

    result = service.validate_and_download(
        source_id=source_id,
        manga_title=manga_title,
        post=post,
        slug=slug,
        chapter_ids=chapter_ids,
        format="images",
        options={
            "quality": "low",
            "includeMetadata": True,
        },
        validate_only=False  # Actually download
    )

    print(f"\nFinal Result:")
    print(json.dumps(result, indent=2))


def test_manual_workflow():
    """
    Example: Manual workflow - search, validate, download separately
    """
    service = HaruNekoDownloadService()

    source_id = "mangahere"
    search_query = "berserk"
    post = "4737"
    slug = "/manga/berserk/"

    print("\n" + "="*60)
    print("MANUAL WORKFLOW EXAMPLE")
    print("="*60)

    # Step 1: Search for manga
    print(f"\n[1] Searching for '{search_query}'...")
    results = service.search_manga(source_id, search_query, page=1, limit=10)
    print(f"Found {len(results)} results")
    for i, manga in enumerate(results[:3], 1):
        print(f"  {i}. {manga.get('title', 'Unknown')} - ID: {manga.get('id', 'N/A')[:50]}...")

    # Step 2: Resolve exact manga by post + slug
    print(f"\n[2] Resolving manga with post={post}, slug={slug}...")
    manga = service.resolve_manga_id(source_id, search_query, post, slug)

    if not manga:
        print("[ERROR] Manga not found!")
        return

    manga_id_raw = manga["id"]
    print(f"Found: {manga.get('title', 'Unknown')}")
    print(f"ID: {manga_id_raw}")

    # Step 3: Fetch chapters
    print(f"\n[3] Fetching chapters...")
    chapters = service.fetch_chapters(source_id, manga_id_raw)
    print(f"Found {len(chapters)} chapters")

    # Display first 5 chapters
    for i, chapter in enumerate(chapters[:5], 1):
        chapter_title = chapter.get("title", "Unknown")
        chapter_id = chapter.get("id", "N/A")
        print(f"  {i}. {chapter_title[:50]} - ID: {chapter_id[:50]}...")

    # Step 4: Validate specific chapters
    if len(chapters) >= 3:
        chapter_ids_to_check = [
            chapters[0]["id"],
            chapters[1]["id"],
            chapters[2]["id"],
        ]

        print(f"\n[4] Validating {len(chapter_ids_to_check)} chapters...")
        validation = service.validate_manga_has_chapters(
            source_id, search_query, post, slug, chapter_ids_to_check
        )

        print(f"Validation: {'SUCCESS' if validation['success'] else 'FAILED'}")
        if not validation['success']:
            print(f"Error: {validation['error']}")
            print(f"Missing: {validation['missing_chapters']}")
        else:
            print(f"All chapters available!")

            # Step 5: Download
            print(f"\n[5] Downloading chapters...")
            download_result = service.download_chapters(
                source_id,
                manga_id_raw,
                chapter_ids_to_check,
                format="images",
                options={"quality": "low", "includeMetadata": True}
            )

            if download_result['success']:
                print("[SUCCESS] Download initiated!")
                print(f"Response: {json.dumps(download_result['response'], indent=2)}")
            else:
                print(f"[ERROR] Download failed: {download_result['error']}")


def test_error_handling():
    """
    Example: Test error handling for missing manga/chapters
    """
    service = HaruNekoDownloadService()

    print("\n" + "="*60)
    print("ERROR HANDLING TESTS")
    print("="*60)

    # Test 1: Non-existent manga
    print("\n[TEST] Non-existent manga...")
    result = service.validate_and_download(
        source_id="mangahere",
        manga_title="ThisMangaDoesNotExist12345",
        post="99999",
        slug="/manga/nonexistent/",
        chapter_ids=["/manga/nonexistent/c001/"],
        validate_only=True
    )
    print(f"Result: {result['validation']['error']}")

    # Test 2: Invalid chapter IDs
    print("\n[TEST] Invalid chapter IDs...")
    result = service.validate_and_download(
        source_id="mangahere",
        manga_title="berserk",
        post="4737",
        slug="/manga/berserk/",
        chapter_ids=["/manga/berserk/c99999/", "/manga/berserk/c99998/"],
        validate_only=True
    )
    print(f"Result: {result['validation']['error']}")
    print(f"Missing: {result['validation']['missing_chapters']}")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║         HaruNeko Download Service - Test Suite              ║
╚══════════════════════════════════════════════════════════════╝

This script tests the HaruNeko API client with several examples.
Make sure the HaruNeko API server is running on localhost:3000

""")

    # Choose which tests to run
    print("Available tests:")
    print("1. Berserk example (validate + download)")
    print("2. Manual workflow (step-by-step)")
    print("3. Error handling tests")
    print("4. Run all tests")

    choice = input("\nSelect test (1-4) or press Enter to run all: ").strip()

    if choice == "1":
        test_berserk_example()
    elif choice == "2":
        test_manual_workflow()
    elif choice == "3":
        test_error_handling()
    else:
        # Run all tests
        test_berserk_example()
        test_manual_workflow()
        test_error_handling()

    print("\n" + "="*60)
    print("Tests completed!")
    print("="*60)
