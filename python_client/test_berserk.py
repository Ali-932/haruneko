#!/usr/bin/env python3
"""
Quick test to debug Berserk chapter fetching
"""

from haruneko_download_service import HaruNekoDownloadService

service = HaruNekoDownloadService()

print("Searching for Berserk on mangahere...\n")
results = service._search_manga("mangahere", "Berserk", page=1, limit=50)

print(f"Found {len(results)} results:\n")
for i, result in enumerate(results[:10], 1):
    print(f"{i}. {result['title']}")
    print(f"   ID: {result['id']}")
    print()

# Find exact match
manga = None
for result in results:
    if result['title'].lower() == "berserk":
        manga = result
        break

if manga:
    print(f"\n✓ Found Berserk!")
    print(f"Title: {manga['title']}")
    print(f"ID: {manga['id']}")
    print(f"ID type: {type(manga['id'])}")
    print(f"\nFetching chapters with debug mode...\n")

    chapters = service._get_chapters("mangahere", manga['id'], debug=True)

    print(f"\n✓ Got {len(chapters)} chapters")

    if chapters:
        print("\nFirst 5 chapters:")
        for ch in chapters[:5]:
            print(f"  - {ch.get('title', 'N/A')}")
else:
    print("\n✗ Berserk not found in results")
