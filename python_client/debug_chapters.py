#!/usr/bin/env python3
"""
Debug script - See what chapters are actually found
"""

from haruneko_download_service import HaruNekoDownloadService

service = HaruNekoDownloadService()

# Get manga info
print("Searching for One Piece on mangahere...")
results = service._search_manga("mangahere", "One Piece", page=1, limit=10)

if not results:
    print("No results found!")
    exit(1)

manga = results[0]
manga_id = manga["id"]

print(f"\nFound: {manga['title']}")
print(f"Getting chapters...")

# Get all chapters
chapters = service._get_chapters("mangahere", manga_id)

print(f"\nTotal chapters: {len(chapters)}")
print("\nFirst 10 chapters:")
for i, ch in enumerate(chapters[:10], 1):
    print(f"{i}. Title: {ch.get('title', 'N/A')}")
    print(f"   Number: {ch.get('number', 'N/A')}")
    print(f"   ID: {ch.get('id', 'N/A')}")
    print()

print("\nLast 10 chapters:")
for i, ch in enumerate(chapters[-10:], 1):
    print(f"{i}. Title: {ch.get('title', 'N/A')}")
    print(f"   Number: {ch.get('number', 'N/A')}")
    print(f"   ID: {ch.get('id', 'N/A')}")
    print()

# Try to find chapters 1, 2, 3
print("\n" + "="*70)
print("Searching for chapters 1, 2, 3 in the chapter list...")
print("="*70)

for search_num in [1, 2, 3]:
    print(f"\nLooking for chapter {search_num}:")
    found = []
    for ch in chapters:
        # Check if chapter.number matches
        if ch.get('number') == search_num:
            found.append(ch)
            print(f"  ✓ Found by number field: {ch.get('title')}")

        # Check if title contains the pattern
        import re
        title = ch.get('title', '')
        patterns = [
            r'(?:Chapter|Ch\.?|Episode|Ep\.?)\s*' + str(search_num) + r'(?:\D|$)',
            r'^' + str(search_num) + r'\s*[-:]',
        ]
        for pattern in patterns:
            if re.search(pattern, title, re.IGNORECASE):
                if ch not in found:
                    found.append(ch)
                    print(f"  ✓ Found by pattern: {title}")

    if not found:
        print(f"  ✗ Chapter {search_num} not found!")
