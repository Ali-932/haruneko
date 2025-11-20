#!/usr/bin/env python3
"""
Test script to fetch chapters for all manga from MangaHere source.
Tracks successes, failures, and reasons for failures.
"""

import requests
import time
from typing import Dict, List, Tuple
from collections import defaultdict
import json


class MangaChapterTester:
    def __init__(self, base_url: str = "http://localhost:3000", source: str = "mangahere"):
        self.base_url = base_url
        self.source = source
        self.results = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'zero_chapters': 0,
            'errors': defaultdict(list),
            'successful_manga': [],
            'failed_manga': []
        }

    def get_all_manga(self, limit: int = 1000) -> List[Dict]:
        """Fetch all manga from the source."""
        print(f"📚 Fetching manga list from {self.source}...")
        all_manga = []
        page = 1
        page_limit = 20

        while True:
            try:
                url = f"{self.base_url}/api/v1/sources/{self.source}/manga"
                params = {'page': page, 'limit': page_limit}

                response = requests.get(url, params=params, timeout=30)

                if response.status_code != 200:
                    print(f"❌ Failed to fetch manga list (page {page}): {response.status_code}")
                    break

                data = response.json()

                if not data.get('success', False):
                    print(f"❌ API returned error: {data.get('error', 'Unknown error')}")
                    break

                manga_list = data.get('data', [])

                if not manga_list:
                    print(f"✅ Reached end of manga list at page {page}")
                    break

                all_manga.extend(manga_list)
                print(f"  📄 Page {page}: fetched {len(manga_list)} manga (total: {len(all_manga)})")

                # Check if we've reached the limit
                if len(all_manga) >= limit:
                    print(f"🛑 Reached limit of {limit} manga")
                    all_manga = all_manga[:limit]
                    break

                # Check if there are more pages
                meta = data.get('meta', {})
                total_pages = meta.get('totalPages', 0)

                if page >= total_pages:
                    print(f"✅ Fetched all {len(all_manga)} manga from {total_pages} pages")
                    break

                page += 1
                time.sleep(0.5)  # Be nice to the server

            except requests.exceptions.Timeout:
                print(f"⏱️  Timeout on page {page}, stopping...")
                break
            except Exception as e:
                print(f"❌ Error fetching page {page}: {e}")
                break

        return all_manga

    def test_manga_chapters(self, manga: Dict) -> Tuple[bool, str, int]:
        """
        Test fetching chapters for a single manga.
        Returns: (success: bool, error_reason: str, chapter_count: int)
        """
        manga_id = manga.get('id')
        manga_title = manga.get('title', 'Unknown')

        try:
            url = f"{self.base_url}/api/v1/sources/{self.source}/manga/{requests.utils.quote(manga_id, safe='')}/chapters"

            response = requests.get(url, timeout=60)

            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg = error_data['error'].get('message', error_msg)
                except:
                    pass
                return False, error_msg, 0

            data = response.json()

            if not data.get('success', False):
                error_msg = data.get('error', {}).get('message', 'Unknown error')
                return False, error_msg, 0

            chapters = data.get('data', [])
            chapter_count = len(chapters)

            if chapter_count == 0:
                return False, "0 chapters returned", 0

            return True, "", chapter_count

        except requests.exceptions.Timeout:
            return False, "Request timeout", 0
        except requests.exceptions.ConnectionError:
            return False, "Connection error", 0
        except Exception as e:
            return False, f"Exception: {str(e)[:100]}", 0

    def run_test(self, manga_limit: int = 50, delay: float = 1.0):
        """Run the test on all manga."""
        print(f"\n{'='*80}")
        print(f"🧪 Starting MangaHere Chapter Fetch Test")
        print(f"{'='*80}\n")

        # Get all manga
        manga_list = self.get_all_manga(limit=manga_limit)

        if not manga_list:
            print("❌ No manga found to test!")
            return

        self.results['total'] = len(manga_list)

        print(f"\n{'='*80}")
        print(f"🔍 Testing {len(manga_list)} manga titles...")
        print(f"{'='*80}\n")

        # Test each manga
        for idx, manga in enumerate(manga_list, 1):
            manga_id = manga.get('id')
            manga_title = manga.get('title', 'Unknown')

            print(f"[{idx}/{len(manga_list)}] Testing: {manga_title}")
            print(f"  ID: {manga_id}")

            success, error_reason, chapter_count = self.test_manga_chapters(manga)

            if success:
                self.results['success'] += 1
                self.results['successful_manga'].append({
                    'title': manga_title,
                    'id': manga_id,
                    'chapters': chapter_count
                })
                print(f"  ✅ SUCCESS: {chapter_count} chapters found\n")
            else:
                self.results['failed'] += 1
                self.results['failed_manga'].append({
                    'title': manga_title,
                    'id': manga_id,
                    'error': error_reason
                })

                if error_reason == "0 chapters returned":
                    self.results['zero_chapters'] += 1

                self.results['errors'][error_reason].append(manga_title)
                print(f"  ❌ FAILED: {error_reason}\n")

            # Delay between requests
            if idx < len(manga_list):
                time.sleep(delay)

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test results summary."""
        print(f"\n{'='*80}")
        print(f"📊 TEST SUMMARY")
        print(f"{'='*80}\n")

        total = self.results['total']
        success = self.results['success']
        failed = self.results['failed']
        zero_chapters = self.results['zero_chapters']

        success_rate = (success / total * 100) if total > 0 else 0

        print(f"Total manga tested:    {total}")
        print(f"✅ Successful:         {success} ({success_rate:.1f}%)")
        print(f"❌ Failed:             {failed} ({100-success_rate:.1f}%)")
        print(f"   └─ Zero chapters:   {zero_chapters}")

        if self.results['errors']:
            print(f"\n{'─'*80}")
            print("📋 FAILURE BREAKDOWN BY ERROR TYPE:")
            print(f"{'─'*80}\n")

            # Sort errors by frequency
            sorted_errors = sorted(
                self.results['errors'].items(),
                key=lambda x: len(x[1]),
                reverse=True
            )

            for error_type, manga_titles in sorted_errors:
                count = len(manga_titles)
                percentage = (count / failed * 100) if failed > 0 else 0
                print(f"❌ {error_type}")
                print(f"   Count: {count} ({percentage:.1f}% of failures)")
                print(f"   Examples: {', '.join(manga_titles[:3])}")
                if len(manga_titles) > 3:
                    print(f"   ... and {len(manga_titles) - 3} more")
                print()

        if self.results['successful_manga']:
            print(f"{'─'*80}")
            print(f"✅ TOP 10 SUCCESSFUL MANGA (by chapter count):")
            print(f"{'─'*80}\n")

            top_manga = sorted(
                self.results['successful_manga'],
                key=lambda x: x['chapters'],
                reverse=True
            )[:10]

            for manga in top_manga:
                print(f"  • {manga['title']}: {manga['chapters']} chapters")

        # Save detailed results to JSON
        output_file = 'manga_test_results.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"\n{'─'*80}")
        print(f"💾 Detailed results saved to: {output_file}")
        print(f"{'='*80}\n")


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description='Test chapter fetching for all manga from MangaHere')
    parser.add_argument('--url', default='http://localhost:3000', help='API base URL')
    parser.add_argument('--source', default='mangahere', help='Source to test')
    parser.add_argument('--limit', type=int, default=50, help='Maximum number of manga to test')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests in seconds')

    args = parser.parse_args()

    tester = MangaChapterTester(base_url=args.url, source=args.source)
    tester.run_test(manga_limit=args.limit, delay=args.delay)


if __name__ == '__main__':
    main()
