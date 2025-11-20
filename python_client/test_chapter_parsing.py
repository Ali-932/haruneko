#!/usr/bin/env python3
"""
Test script to verify chapter parsing fix
"""
import re
from typing import Optional, Dict, List


def resolve_chapter_old(chapters: List[Dict], user_input: str) -> Optional[Dict]:
    """OLD buggy version - extracts first number (volume instead of chapter)"""
    normalized = user_input.strip().lower()

    try:
        user_number = int(''.join(filter(str.isdigit, normalized)))
    except (ValueError, TypeError):
        return None

    for chap in chapters:
        title = chap["title"].strip().lower()
        chapter_numbers = re.findall(r'\d+', title)

        if chapter_numbers:
            try:
                chapter_number = int(chapter_numbers[0])  # BUG: Takes first number
                if user_number == chapter_number:
                    return chap
            except (ValueError, TypeError):
                continue

    return None


def resolve_chapter_new(chapters: List[Dict], user_input: str) -> Optional[Dict]:
    """NEW fixed version - extracts chapter number after 'Ch.' keyword"""
    normalized = user_input.strip().lower()

    try:
        user_number = float(''.join(filter(lambda c: c.isdigit() or c == '.', normalized)))
    except (ValueError, TypeError):
        return None

    for chap in chapters:
        title = chap["title"].strip().lower()

        # Look for chapter number after "ch" keyword
        chapter_match = re.search(r'ch\.?(\d+(?:\.\d+)?)', title)

        if chapter_match:
            try:
                chapter_number = float(chapter_match.group(1))

                # Exact match first (e.g., 8.1 matches only 8.1)
                if user_number == chapter_number:
                    return chap

                # Integer match only if both are integers (e.g., 8 matches 8.0 but not 8.1)
                if (user_number == int(user_number) and
                    chapter_number == int(chapter_number) and
                    int(user_number) == int(chapter_number)):
                    return chap
            except (ValueError, TypeError):
                continue

    return None


def test_parsing():
    """Test chapter parsing with real data from mangahere"""

    # Sample chapter data from One Piece (from the JSON you provided)
    one_piece_chapters = [
        {"id": "/manga/one_piece/v01/c008/1.html", "title": "Vol.01 Ch.008 - Nami                                Aug 01,2016"},
        {"id": "/manga/one_piece/v01/c007/1.html", "title": "Vol.01 Ch.007                                Jun 08,2008"},
        {"id": "/manga/one_piece/v01/c006/1.html", "title": "Vol.01 Ch.006                                Jun 08,2008"},
        {"id": "/manga/one_piece/v01/c005/1.html", "title": "Vol.01 Ch.005                                Jun 08,2008"},
        {"id": "/manga/one_piece/v01/c004/1.html", "title": "Vol.01 Ch.004                                Jun 08,2008"},
        {"id": "/manga/one_piece/v01/c003/1.html", "title": "Vol.01 Ch.003                                Jun 08,2008"},
        {"id": "/manga/one_piece/v01/c002/1.html", "title": "Vol.01 Ch.002                                Jun 08,2008"},
        {"id": "/manga/one_piece/v01/c001/1.html", "title": "Vol.01 Ch.001 - Romance Dawn                                Jun 08,2008"},
        {"id": "/manga/one_piece/v02/c014/1.html", "title": "Vol.02 Ch.014 - Reckless                                Oct 18,2007"},
        {"id": "/manga/one_piece/v02/c013/1.html", "title": "Vol.02 Ch.013                                Oct 18,2007"},
    ]

    # Test cases: (user_input, expected_chapter_id)
    test_cases = [
        ("1", "/manga/one_piece/v01/c001/1.html"),
        ("2", "/manga/one_piece/v01/c002/1.html"),
        ("8", "/manga/one_piece/v01/c008/1.html"),
        ("14", "/manga/one_piece/v02/c014/1.html"),
    ]

    print("="*80)
    print("CHAPTER PARSING TEST")
    print("="*80)
    print()

    for user_input, expected_id in test_cases:
        print(f"Test: Requesting chapter '{user_input}'")

        # Test old (buggy) version
        old_result = resolve_chapter_old(one_piece_chapters, user_input)
        if old_result:
            is_correct = old_result['id'] == expected_id
            symbol = "✓" if is_correct else "✗"
            print(f"  OLD (buggy):  {symbol} {old_result['title'].strip()}")
        else:
            print(f"  OLD (buggy):  ✗ None found")

        # Test new (fixed) version
        new_result = resolve_chapter_new(one_piece_chapters, user_input)
        if new_result:
            is_correct = new_result['id'] == expected_id
            symbol = "✓" if is_correct else "✗"
            print(f"  NEW (fixed):  {symbol} {new_result['title'].strip()}")
        else:
            print(f"  NEW (fixed):  ✗ None found")

        print()

    # Additional test cases with decimal chapters
    print("="*80)
    print("DECIMAL CHAPTER TEST")
    print("="*80)
    print()

    # Test with decimal chapters appearing in different orders
    decimal_chapters = [
        {"id": "/manga/ana_satsujin/c132.5/1.html", "title": "Ch.132.5                                Mar 16,2022"},
        {"id": "/manga/ana_satsujin/c132/1.html", "title": "Ch.132                                Sep 14,2016"},
        {"id": "/manga/69/v01/c008.1/1.html", "title": "Vol.01 Ch.008.1 - extra                                Jun 08,2008"},
        {"id": "/manga/69/v01/c008/1.html", "title": "Vol.01 Ch.008                                Jun 08,2008"},
    ]

    decimal_tests = [
        ("8", "/manga/69/v01/c008/1.html"),
        ("8.1", "/manga/69/v01/c008.1/1.html"),
        ("132", "/manga/ana_satsujin/c132/1.html"),
        ("132.5", "/manga/ana_satsujin/c132.5/1.html"),
    ]

    for user_input, expected_id in decimal_tests:
        print(f"Test: Requesting chapter '{user_input}'")
        result = resolve_chapter_new(decimal_chapters, user_input)
        if result:
            is_correct = result['id'] == expected_id
            symbol = "✓" if is_correct else "✗"
            print(f"  Result: {symbol} {result['title'].strip()}")
        else:
            print(f"  Result: ✗ None found")
        print()


if __name__ == "__main__":
    test_parsing()
