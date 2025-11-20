"""
Script to collect chapter title patterns from multiple manga sources
This will help determine the best way to parse chapter numbers from titles
"""
import json
import time
import requests
from typing import Dict, List, Optional
from pathlib import Path


class ChapterPatternCollector:
    """Collect chapter title patterns from various manga sources"""

    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.collected_data = []

    def _request_with_retry(self, request_func, max_retries: int = 5, initial_delay: float = 2.0):
        """Execute request with retry logic"""
        delay = initial_delay
        last_error = None

        for attempt in range(max_retries):
            try:
                return request_func()
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code in [429, 500, 502, 503, 504]:
                    last_error = e
                    if attempt < max_retries - 1:
                        print(f"[WARN] HTTP {e.response.status_code} - Retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        raise
                else:
                    raise
            except (requests.ConnectionError, requests.Timeout) as e:
                last_error = e
                if attempt < max_retries - 1:
                    print(f"[WARN] {type(e).__name__} - Retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise

        if last_error:
            raise last_error

    def get_sources(self) -> List[str]:
        """Get list of available sources"""
        def _make_request():
            resp = self.session.get(f"{self.base_url}/api/v1/sources", timeout=30)
            resp.raise_for_status()
            return resp

        try:
            resp = self._request_with_retry(_make_request)
            data = resp.json()

            # Extract source IDs
            if isinstance(data, dict) and data.get('success'):
                sources = data.get('data', [])
                return [s.get('id') for s in sources if s.get('id')]
            elif isinstance(data, list):
                return [s.get('id') for s in data if s.get('id')]

            return []
        except Exception as e:
            print(f"[ERROR] Failed to get sources: {e}")
            return []

    def search_manga(self, query: str, source: str) -> List[Dict]:
        """Search for manga by title"""
        def _make_request():
            resp = self.session.get(
                f"{self.base_url}/api/v1/sources/{source}/search",
                params={"q": query},
                timeout=30
            )
            resp.raise_for_status()
            return resp

        try:
            resp = self._request_with_retry(_make_request)
            data = resp.json()

            if isinstance(data, dict) and data.get('success'):
                return data.get('data', [])
            elif isinstance(data, list):
                return data

            return []
        except Exception as e:
            print(f"[ERROR] Search failed for '{query}' on {source}: {e}")
            return []

    def fetch_chapters(self, manga_id: str, source: str) -> List[Dict]:
        """Fetch chapter list for a manga"""
        def _make_request():
            encoded_manga_id = requests.utils.quote(manga_id, safe='')
            resp = self.session.get(
                f"{self.base_url}/api/v1/sources/{source}/manga/{encoded_manga_id}/chapters",
                timeout=30
            )
            resp.raise_for_status()
            return resp

        try:
            resp = self._request_with_retry(_make_request)
            data = resp.json()

            if isinstance(data, dict) and data.get('success'):
                return data.get('data', [])
            elif isinstance(data, list):
                return data

            return []
        except Exception as e:
            print(f"[ERROR] Failed to fetch chapters for {manga_id}: {e}")
            return []

    def collect_from_source(self, source: str, manga_queries: List[str], chapters_per_manga: int = 3) -> int:
        """
        Collect chapter patterns from a source

        Args:
            source: Source identifier
            manga_queries: List of manga titles to search for
            chapters_per_manga: Number of chapters to collect per manga

        Returns:
            Number of manga successfully collected
        """
        collected_count = 0

        print(f"\n{'='*70}")
        print(f"Processing source: {source}")
        print(f"{'='*70}")

        for query in manga_queries:
            try:
                print(f"\n[INFO] Searching for: {query}")

                # Search for manga
                results = self.search_manga(query, source)
                if not results:
                    print(f"[SKIP] No results found for '{query}'")
                    continue

                # Take the first result (usually most relevant)
                manga = results[0]
                manga_id = manga.get('id')
                manga_title = manga.get('title')

                if not manga_id:
                    print(f"[SKIP] No manga ID for '{query}'")
                    continue

                print(f"[INFO] Found: {manga_title} (ID: {manga_id})")

                # Fetch chapters
                chapters = self.fetch_chapters(manga_id, source)
                if not chapters:
                    print(f"[SKIP] No chapters found for '{manga_title}'")
                    continue

                print(f"[INFO] Found {len(chapters)} chapters")

                # Collect first N chapters
                sample_chapters = chapters[:chapters_per_manga]

                chapter_data = {
                    "source": source,
                    "manga_id": manga_id,
                    "manga_title": manga_title,
                    "total_chapters": len(chapters),
                    "sample_chapters": []
                }

                for i, chapter in enumerate(sample_chapters, 1):
                    chapter_info = {
                        "index": i,
                        "id": chapter.get('id'),
                        "title": chapter.get('title', ''),
                        "full_chapter_data": chapter
                    }
                    chapter_data["sample_chapters"].append(chapter_info)
                    print(f"  [{i}] {chapter.get('title', 'NO TITLE')}")

                self.collected_data.append(chapter_data)
                collected_count += 1

                # Rate limiting - be nice to the API
                time.sleep(0.5)

            except Exception as e:
                print(f"[ERROR] Failed to process '{query}': {e}")
                continue

        return collected_count

    def save_results(self, output_file: str = "chapter_patterns.json"):
        """Save collected data to JSON file"""
        output_path = Path(output_file)

        with output_path.open('w', encoding='utf-8') as f:
            json.dump(self.collected_data, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*70}")
        print(f"RESULTS SAVED")
        print(f"{'='*70}")
        print(f"File: {output_path.absolute()}")
        print(f"Total manga collected: {len(self.collected_data)}")

        # Count total chapters
        total_chapters = sum(len(m["sample_chapters"]) for m in self.collected_data)
        print(f"Total chapters collected: {total_chapters}")

        # Show sample of titles
        print(f"\n{'='*70}")
        print("SAMPLE CHAPTER TITLES")
        print(f"{'='*70}")
        for manga in self.collected_data[:5]:
            print(f"\nManga: {manga['manga_title']} (source: {manga['source']})")
            for ch in manga["sample_chapters"]:
                print(f"  - {ch['title']}")


def main():
    """Main collection script"""

    print("="*70)
    print("CHAPTER PATTERN COLLECTION SCRIPT")
    print("="*70)
    print(f"Source: mangahere only")
    print(f"Chapters per manga: 3")
    print("="*70)

    collector = ChapterPatternCollector()

    # Use only mangahere source
    source = "mangahere"
    print(f"\n[INFO] Using source: {source}")

    # Fetch manga dynamically from the source using varied search queries
    print("[INFO] Fetching manga titles from source...")

    # Use common search terms to get diverse manga
    search_terms = [
        "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
        "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
        "one", "two", "three", "love", "death", "life", "world", "hero",
        "god", "demon", "dragon", "king", "queen", "blood", "dark", "light"
    ]

    manga_titles = []
    seen_manga_ids = set()
    target_manga_count = 150

    for term in search_terms:
        if len(manga_titles) >= target_manga_count:
            break

        print(f"[INFO] Searching with term: '{term}'")
        results = collector.search_manga(term, source)

        for manga in results:
            manga_id = manga.get('id')
            manga_title = manga.get('title')

            # Skip duplicates
            if manga_id in seen_manga_ids:
                continue

            seen_manga_ids.add(manga_id)
            manga_titles.append(manga_title)

            if len(manga_titles) >= target_manga_count:
                break

        # Rate limiting
        time.sleep(0.3)

    print(f"\n[INFO] Fetched {len(manga_titles)} unique manga titles from {source}")
    print(f"[INFO] Expected total chapters: ~{len(manga_titles) * 3}")

    # Collect from all manga on mangahere
    total_collected = collector.collect_from_source(source, manga_titles, chapters_per_manga=3)

    # Save results
    collector.save_results("chapter_patterns.json")

    print(f"\n{'='*70}")
    print("COLLECTION COMPLETE")
    print(f"{'='*70}")
    print(f"Total manga collected: {total_collected}")
    print(f"Output file: chapter_patterns.json")
    print(f"\nNext steps:")
    print(f"1. Review the chapter_patterns.json file")
    print(f"2. Analyze the patterns to determine best parsing strategy")
    print(f"3. Update the resolve_chapter() method accordingly")


if __name__ == "__main__":
    main()
