"""
MangaLek Chapter Testing Service - Test chapter fetching for all manga
"""
import argparse
import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup


API_KEY = "dd2eb612-b6df-4db6-a90c-3fe484270750"
SEARCH_URL = "https://api.mangaslayers.com/manga/search"
CHAPTER_LIST_URL = "https://lekmanga.net/wp-admin/admin-ajax.php"


class MangaLekChapterTester:
    """Test chapter fetching for all manga from MangaLek service"""

    def __init__(
        self,
        cookie: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.session = session or requests.Session()

        self.api_headers = {
            "authorization": "",
            "x-api-key": API_KEY,
            "content-type": "application/json; charset=UTF-8",
            "user-agent": "okhttp/5.0.0-alpha.12",
        }

        self.ajax_headers = {
            "content-type": "application/x-www-form-urlencoded",
            "user-agent": "okhttp/5.0.0-alpha.12",
            "accept-encoding": "gzip, deflate",
        }

        if cookie:
            self.ajax_headers["cookie"] = cookie

        self.results = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'zero_chapters': 0,
            'errors': defaultdict(list),
            'successful_manga': [],
            'failed_manga': []
        }

    def _request_with_retry(
        self,
        request_func,
        max_retries: int = 10,
        initial_delay: float = 3.0
    ):
        """
        Execute a request function with retry logic for 429 errors

        Args:
            request_func: Function that makes the HTTP request
            max_retries: Maximum number of retry attempts (default: 10)
            initial_delay: Initial delay in seconds, doubles with each retry (default: 3s)

        Returns:
            Response from the request

        Raises:
            requests.HTTPError: If non-429 error or max retries exceeded
        """
        delay = initial_delay
        last_error = None

        for attempt in range(max_retries):
            try:
                return request_func()
            except requests.HTTPError as e:
                # Check if it's a 429 Too Many Requests error
                if e.response is not None and e.response.status_code == 429:
                    last_error = e
                    if attempt < max_retries - 1:  # Don't sleep on the last attempt
                        print(f"  [WARN] 429 Too Many Requests - Retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        delay *= 2  # Double the delay for next retry
                    else:
                        print(f"  [ERROR] 429 Too Many Requests - Max retries ({max_retries}) exceeded")
                        raise
                else:
                    # For non-429 errors, raise immediately
                    raise
            except Exception:
                # For non-HTTP errors, raise immediately
                raise

        # If we get here, all retries failed with 429
        if last_error:
            raise last_error

    def search_all_manga(self, page: int = 1, size: int = 100) -> List[Dict]:
        """Search for all manga with pagination support"""
        payload = {"genres": [], "query": ""}
        params = {"page": page, "size": size}

        def _make_request():
            resp = self.session.post(
                SEARCH_URL,
                params=params,
                headers=self.api_headers,
                json=payload,
                timeout=15
            )
            resp.raise_for_status()
            return resp

        resp = self._request_with_retry(_make_request)
        return resp.json()

    def get_all_manga(self, limit: int = 1000) -> List[Dict]:
        """
        Fetch all available manga with pagination

        Args:
            limit: Maximum number of manga to fetch

        Returns:
            List of manga dictionaries
        """
        all_manga = []
        page = 1
        page_size = 100

        print(f"Fetching manga from MangaLek API (limit: {limit})...")

        while len(all_manga) < limit:
            try:
                print(f"  Fetching page {page}...")
                results = self.search_all_manga(page=page, size=page_size)

                if not results:
                    print("  No more results found")
                    break

                all_manga.extend(results)
                print(f"  Got {len(results)} manga (total: {len(all_manga)})")

                if len(results) < page_size:
                    print("  Reached last page")
                    break

                page += 1
                time.sleep(0.5)  # Small delay between pagination requests

            except Exception as e:
                print(f"  Error fetching page {page}: {e}")
                break

        return all_manga[:limit]

    def fetch_chapter_listing_html(self, manga_id: int) -> str:
        """Fetch chapter list HTML from lekmanga with retry logic for 429 errors"""
        payload = {"action": "manga_get_chapters", "manga": str(manga_id)}

        def _make_request():
            resp = self.session.post(
                CHAPTER_LIST_URL,
                headers=self.ajax_headers,
                data=payload,
                timeout=15
            )
            resp.raise_for_status()
            return resp

        resp = self._request_with_retry(_make_request)
        return resp.text

    def parse_chapter_list(self, html: str) -> List[Dict]:
        """Parse chapter list from HTML"""
        soup = BeautifulSoup(html, "html.parser")
        chapters = []

        for anchor in soup.select("li.wp-manga-chapter > a"):
            title_text = anchor.get_text(strip=True)
            href = anchor.get("href", "")

            chapters.append({
                "title": title_text,
                "href": href,
            })

        return chapters

    def test_manga_chapters(self, manga: Dict) -> Tuple[bool, str, int]:
        """
        Test chapter fetching for a single manga

        Args:
            manga: Manga dictionary with _id and title

        Returns:
            Tuple of (success, error_reason, chapter_count)
        """
        manga_id = manga.get("_id")
        manga_title = manga.get("title", "Unknown")

        try:
            # Fetch chapter list
            chapter_html = self.fetch_chapter_listing_html(manga_id)

            if not chapter_html or not chapter_html.strip():
                return False, "Empty response from chapter list API", 0

            # Parse chapters
            chapters = self.parse_chapter_list(chapter_html)
            chapter_count = len(chapters)

            if chapter_count == 0:
                return False, "Zero chapters returned", 0

            return True, "", chapter_count

        except requests.HTTPError as e:
            if e.response is not None:
                if e.response.status_code == 429:
                    return False, "Rate limit exceeded (429)", 0
                elif e.response.status_code == 404:
                    return False, "Manga not found (404)", 0
                elif e.response.status_code >= 500:
                    return False, f"Server error ({e.response.status_code})", 0
                else:
                    return False, f"HTTP error {e.response.status_code}", 0
            return False, "HTTP error (no response)", 0

        except requests.Timeout:
            return False, "Request timeout", 0

        except Exception as e:
            error_msg = str(e)
            # Categorize common errors
            if "Connection" in error_msg or "connection" in error_msg:
                return False, "Connection error", 0
            elif "timeout" in error_msg.lower():
                return False, "Timeout", 0
            elif "JSON" in error_msg or "json" in error_msg:
                return False, "Invalid JSON response", 0
            else:
                return False, f"Unknown error: {error_msg[:50]}", 0

    def run_test(self, manga_limit: int = 50, delay: float = 1.0):
        """
        Run comprehensive test on all manga

        Args:
            manga_limit: Maximum number of manga to test
            delay: Delay in seconds between each test
        """
        print(f"\n{'='*70}")
        print(f"MangaLek Chapter Fetching Test")
        print(f"{'='*70}\n")

        # Fetch all manga
        all_manga = self.get_all_manga(limit=manga_limit)

        if not all_manga:
            print("\nNo manga found to test!")
            return

        total = len(all_manga)
        print(f"\nTesting {total} manga titles...\n")

        # Test each manga
        for idx, manga in enumerate(all_manga, 1):
            manga_id = manga.get("_id")
            manga_title = manga.get("title", "Unknown")

            print(f"[{idx}/{total}] Testing: {manga_title[:50]}...")

            success, error_reason, chapter_count = self.test_manga_chapters(manga)

            self.results['total'] += 1

            if success:
                self.results['success'] += 1
                self.results['successful_manga'].append({
                    'id': manga_id,
                    'title': manga_title,
                    'chapter_count': chapter_count
                })
                print(f"  ✓ Success - {chapter_count} chapters found")
            else:
                self.results['failed'] += 1
                if error_reason == "Zero chapters returned":
                    self.results['zero_chapters'] += 1

                self.results['errors'][error_reason].append({
                    'id': manga_id,
                    'title': manga_title
                })
                self.results['failed_manga'].append({
                    'id': manga_id,
                    'title': manga_title,
                    'error': error_reason
                })
                print(f"  ✗ Failed - {error_reason}")

            # Rate limiting delay
            if idx < total:
                time.sleep(delay)

        print(f"\n{'='*70}")
        print("Test completed!")
        print(f"{'='*70}\n")

    def print_summary(self):
        """Print detailed summary of test results"""
        total = self.results['total']
        success = self.results['success']
        failed = self.results['failed']
        zero_chapters = self.results['zero_chapters']

        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)

        # Overall statistics
        print(f"\nTotal manga tested: {total}")
        print(f"Successful: {success} ({(success/total*100) if total > 0 else 0:.1f}%)")
        print(f"Failed: {failed} ({(failed/total*100) if total > 0 else 0:.1f}%)")
        print(f"  - Zero chapters: {zero_chapters}")

        # Error breakdown
        if self.results['errors']:
            print("\n" + "-"*70)
            print("FAILURE BREAKDOWN BY ERROR TYPE")
            print("-"*70)

            for error_type, manga_list in sorted(
                self.results['errors'].items(),
                key=lambda x: len(x[1]),
                reverse=True
            ):
                count = len(manga_list)
                percentage = (count / total * 100) if total > 0 else 0
                print(f"\n{error_type}: {count} ({percentage:.1f}%)")

                # Show first 3 examples
                for manga in manga_list[:3]:
                    print(f"  - {manga['title'][:60]}")

                if len(manga_list) > 3:
                    print(f"  ... and {len(manga_list) - 3} more")

        # Top successful manga
        if self.results['successful_manga']:
            print("\n" + "-"*70)
            print("TOP 10 SUCCESSFUL MANGA (by chapter count)")
            print("-"*70)

            sorted_manga = sorted(
                self.results['successful_manga'],
                key=lambda x: x['chapter_count'],
                reverse=True
            )[:10]

            for idx, manga in enumerate(sorted_manga, 1):
                print(f"{idx:2d}. {manga['title'][:50]:50s} - {manga['chapter_count']:4d} chapters")

        # Save to JSON
        output_file = "mangalek_test_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'total': total,
                    'success': success,
                    'failed': failed,
                    'zero_chapters': zero_chapters,
                    'success_rate': f"{(success/total*100) if total > 0 else 0:.2f}%"
                },
                'errors': {
                    error_type: {
                        'count': len(manga_list),
                        'manga': manga_list
                    }
                    for error_type, manga_list in self.results['errors'].items()
                },
                'successful_manga': sorted(
                    self.results['successful_manga'],
                    key=lambda x: x['chapter_count'],
                    reverse=True
                ),
                'failed_manga': self.results['failed_manga']
            }, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*70}")
        print(f"Detailed results saved to: {output_file}")
        print(f"{'='*70}\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Test chapter fetching for all MangaLek manga"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of manga to test (default: 50)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between requests (default: 1.0)"
    )
    parser.add_argument(
        "--cookie",
        type=str,
        default=None,
        help="Optional cookie string for authenticated requests"
    )

    args = parser.parse_args()

    # Create tester and run
    tester = MangaLekChapterTester(cookie=args.cookie)
    tester.run_test(manga_limit=args.limit, delay=args.delay)
    tester.print_summary()


if __name__ == "__main__":
    main()
