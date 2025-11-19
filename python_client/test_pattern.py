#!/usr/bin/env python3
"""Test if the regex patterns match the actual chapter titles"""

import re

# Actual chapter titles from mangahere
test_titles = [
    "Vol.01 Ch.001 - Romance Dawn",
    "Vol.01 Ch.002 - They call him",
    "Vol.01 Ch.003 - Enter Zolo: Pirate Hunter",
    "Vol.98 Ch.1165",
]

patterns = [
    r'(?:Chapter|Ch\.?|Episode|Ep\.?)\s*(\d+(?:\.\d+)?)',  # "Chapter 1", "Ch.828"
    r'^(\d+(?:\.\d+)?)\s*[-:]',  # "1 -", "1.5:"
    r'^(\d+(?:\.\d+)?)\s*$',  # Just a number
]

print("Testing chapter matching patterns:\n")

for title in test_titles:
    print(f"Title: {title}")

    for i, pattern in enumerate(patterns, 1):
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            chapter_num = float(match.group(1))
            print(f"  ✓ Pattern {i} matched: extracted {match.group(1)} → {chapter_num}")
            break
    else:
        print(f"  ✗ No pattern matched!")
    print()

print("\n" + "="*70)
print("Testing specific chapter lookups:")
print("="*70)

requested_chapters = [1, 2, 3]

for requested in requested_chapters:
    print(f"\nLooking for chapter {requested}:")
    found = False

    for title in test_titles:
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                try:
                    chapter_num = float(match.group(1))
                    if chapter_num == float(requested):
                        print(f"  ✓ FOUND in: {title}")
                        print(f"    Extracted: {match.group(1)} → {chapter_num}")
                        found = True
                        break
                except (ValueError, IndexError):
                    pass
        if found:
            break

    if not found:
        print(f"  ✗ NOT FOUND in test titles")
