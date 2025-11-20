"""
Haruneko Manga Download Service - Production service for downloading manga chapters
"""
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests


class HarunekoMangaService:
    """Production service for downloading manga chapters via Haruneko API"""

    def __init__(
        self,
        base_url: str = "http://localhost:3000",
        download_root: str = "downloads",
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url.rstrip('/')
        self.session = session or requests.Session()
        self.download_root = Path(download_root)
        self.download_root.mkdir(parents=True, exist_ok=True)

    def _request_with_retry(
        self,
        request_func,
        max_retries: int = 10,
        initial_delay: float = 3.0
    ):
        """
        Execute a request function with retry logic for 429 errors and network failures

        Args:
            request_func: Function that makes the HTTP request
            max_retries: Maximum number of retry attempts (default: 10)
            initial_delay: Initial delay in seconds, doubles with each retry (default: 3s)

        Returns:
            Response from the request

        Raises:
            requests.HTTPError: If non-retryable error or max retries exceeded
        """
        delay = initial_delay
        last_error = None

        for attempt in range(max_retries):
            try:
                return request_func()
            except requests.HTTPError as e:
                # Retry on 429 (rate limit) and 5xx (server errors)
                if e.response is not None and e.response.status_code in [429, 500, 502, 503, 504]:
                    last_error = e
                    if attempt < max_retries - 1:
                        print(f"[WARN] HTTP {e.response.status_code} - Retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                    else:
                        print(f"[ERROR] HTTP {e.response.status_code} - Max retries ({max_retries}) exceeded")
                        raise
                else:
                    # For non-retryable errors, raise immediately
                    raise
            except (requests.ConnectionError, requests.Timeout) as e:
                # Retry on connection errors and timeouts
                last_error = e
                if attempt < max_retries - 1:
                    print(f"[WARN] {type(e).__name__} - Retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    delay *= 2
                else:
                    print(f"[ERROR] {type(e).__name__} - Max retries ({max_retries}) exceeded")
                    raise
            except Exception:
                # For other errors, raise immediately
                raise

        # If we get here, all retries failed
        if last_error:
            raise last_error

    # 1. Search for manga ------------------------------------------------------
    def search_manga(self, query: str, source: str) -> List[Dict]:
        """
        Search for manga by title from a specific source

        Args:
            query: Manga title to search for
            source: Source identifier (e.g., 'mangahere', 'mangafox')

        Returns:
            List of manga dictionaries
        """
        def _make_request():
            resp = self.session.get(
                f"{self.base_url}/api/v1/sources/{source}/search",
                params={"query": query},
                timeout=30
            )
            resp.raise_for_status()
            return resp

        resp = self._request_with_retry(_make_request)
        data = resp.json()

        # Handle API response format
        if isinstance(data, dict) and data.get('success'):
            return data.get('data', [])
        elif isinstance(data, list):
            return data
        else:
            return []

    @staticmethod
    def _normalize_title(title: str) -> str:
        """
        Normalize title by removing punctuation and extra spaces
        Used for fuzzy matching when exact match fails

        Examples:
            "Namaikizakari." -> "namaikizakari"
            "Cheeky Brat!" -> "cheekybrat"
            "One-Punch Man" -> "onepunchman"
        """
        normalized = re.sub(r'[^\w\s]', '', title.lower())
        normalized = re.sub(r'\s+', '', normalized)
        return normalized

    def resolve_manga_id(self, query: str, source: str) -> Optional[Dict]:
        """
        Find manga by EXACT match first, then normalized match (case-insensitive)

        Tries two matching strategies:
        1. Exact match: "Namaikizakari." matches "Namaikizakari." exactly
        2. Normalized match: "Namaikizakari." matches "Namaikizakari" (no punctuation)

        Args:
            query: Manga title to search for
            source: Source identifier

        Returns:
            Manga dictionary or None if not found
        """
        results = self.search_manga(query, source)
        if not results:
            return None

        # Strategy 1: Try exact match first (case-insensitive)
        normalized_query = query.strip().lower()
        for hit in results:
            if hit["title"].strip().lower() == normalized_query:
                print(f"[INFO] Found exact match: '{hit['title']}'")
                return hit

        # Strategy 2: Try normalized match (strip punctuation)
        normalized_query_fuzzy = self._normalize_title(query)
        for hit in results:
            if self._normalize_title(hit["title"]) == normalized_query_fuzzy:
                print(f"[INFO] Found normalized match: '{hit['title']}' (searched for '{query}')")
                return hit

        # No match found
        return None

    # 2. Get chapter list ------------------------------------------------------
    def fetch_chapters(self, manga_id: str, source: str) -> List[Dict]:
        """
        Fetch chapter list for a manga

        Args:
            manga_id: Manga identifier
            source: Source identifier

        Returns:
            List of chapter dictionaries
        """
        import requests

        def _make_request():
            # URL encode the manga_id to handle special characters
            encoded_manga_id = requests.utils.quote(manga_id, safe='')
            resp = self.session.get(
                f"{self.base_url}/api/v1/sources/{source}/manga/{encoded_manga_id}/chapters",
                timeout=30
            )
            resp.raise_for_status()
            return resp

        resp = self._request_with_retry(_make_request)
        data = resp.json()

        # Handle API response format
        if isinstance(data, dict) and data.get('success'):
            return data.get('data', [])
        elif isinstance(data, list):
            return data
        else:
            return []

    def resolve_chapter(
        self,
        chapters: List[Dict],
        user_input: str
    ) -> Optional[Dict]:
        """
        Find chapter by number or title

        Args:
            chapters: List of chapter dictionaries
            user_input: Chapter number or title to find

        Returns:
            Chapter dictionary or None if not found
        """
        normalized = user_input.strip().lower()

        # Try exact match first
        for chap in chapters:
            if chap["title"].strip().lower() == normalized:
                return chap

        # Extract number from user input (handles "1", "001", etc.)
        try:
            user_number = int(''.join(filter(str.isdigit, normalized)))
        except (ValueError, TypeError):
            return None

        # Try to match by chapter number (handles various formats)
        for chap in chapters:
            title = chap["title"].strip().lower()
            chapter_numbers = re.findall(r'\d+', title)

            if chapter_numbers:
                try:
                    chapter_number = int(chapter_numbers[0])
                    if user_number == chapter_number:
                        return chap
                except (ValueError, TypeError):
                    continue

        return None

    # 3. Download via queue system --------------------------------------------
    def queue_download(
        self,
        manga_id: str,
        chapter_id: str,
        source: str,
        output_path: Optional[str] = None
    ) -> Dict:
        """
        Queue a chapter for download via Haruneko download API

        Args:
            manga_id: Manga identifier
            chapter_id: Chapter identifier
            source: Source identifier
            output_path: Optional output path for download

        Returns:
            Download queue response with download ID
        """
        def _make_request():
            payload = {
                "source": source,
                "mangaId": manga_id,
                "chapterId": chapter_id
            }
            if output_path:
                payload["outputPath"] = output_path

            resp = self.session.post(
                f"{self.base_url}/api/v1/downloads",
                json=payload,
                timeout=30
            )
            resp.raise_for_status()
            return resp

        resp = self._request_with_retry(_make_request)
        data = resp.json()

        # Handle API response format
        if isinstance(data, dict) and data.get('success'):
            return data.get('data', {})
        else:
            return data

    def get_download_status(self, download_id: str) -> Dict:
        """
        Get status of a queued download

        Args:
            download_id: Download identifier

        Returns:
            Download status information
        """
        def _make_request():
            resp = self.session.get(
                f"{self.base_url}/api/v1/downloads/{download_id}",
                timeout=30
            )
            resp.raise_for_status()
            return resp

        resp = self._request_with_retry(_make_request)
        data = resp.json()

        # Handle API response format
        if isinstance(data, dict) and data.get('success'):
            return data.get('data', {})
        else:
            return data

    def wait_for_download(
        self,
        download_id: str,
        poll_interval: float = 2.0,
        max_wait: int = 600
    ) -> Dict:
        """
        Wait for a download to complete, polling for status

        Args:
            download_id: Download identifier
            poll_interval: Seconds between status checks (default: 2.0)
            max_wait: Maximum seconds to wait (default: 600 = 10 minutes)

        Returns:
            Dict with success status, error message, and final status
        """
        start_time = time.time()
        attempts = 0

        while True:
            attempts += 1
            elapsed = time.time() - start_time

            # Check timeout
            if elapsed > max_wait:
                return {
                    "success": False,
                    "error": f"Download timed out after {max_wait}s",
                    "status": "timeout",
                    "download_id": download_id
                }

            try:
                # Get current status
                status_data = self.get_download_status(download_id)
                status = status_data.get('status', 'unknown')

                print(f"[POLL] Attempt {attempts} ({elapsed:.1f}s) - Status: {status}")

                # Check for completion
                if status == 'completed':
                    return {
                        "success": True,
                        "error": None,
                        "status": status,
                        "download_id": download_id,
                        "file_path": status_data.get('filePath'),
                        "data": status_data
                    }
                elif status in ['failed', 'error', 'cancelled']:
                    error_msg = status_data.get('error', f'Download {status}')
                    return {
                        "success": False,
                        "error": error_msg,
                        "status": status,
                        "download_id": download_id,
                        "data": status_data
                    }
                elif status in ['queued', 'downloading', 'processing', 'pending']:
                    # Still in progress, keep polling
                    progress = status_data.get('progress', 0)
                    print(f"  Progress: {progress}%")
                    time.sleep(poll_interval)
                else:
                    # Unknown status, keep polling but warn
                    print(f"  [WARN] Unknown status: {status}")
                    time.sleep(poll_interval)

            except Exception as e:
                print(f"[ERROR] Status check failed: {str(e)}")
                # Don't fail immediately on status check errors
                time.sleep(poll_interval)

    # NOTE: Haruneko API uses a queue-based download system
    # Direct image URL fetching is not available via HTTP API
    # Use queue_download() and get_download_status() instead

    # 4. Legacy compatibility method -------------------------------------------
    def download_images(
        self,
        manga_title: str,
        chapter_title: str,
        image_urls: List[str],
        dry_run: bool = False,
    ) -> Path:
        """
        Download chapter images to disk

        Args:
            manga_title: Manga title for folder name
            chapter_title: Chapter title for folder name
            image_urls: List of image URLs to download
            dry_run: If True, only preview without downloading

        Returns:
            Path to the download folder
        """
        sanitized_title = re.sub(r"[^A-Za-z0-9_\-\.]+", "_", manga_title).strip("_") or "manga"

        # Extract chapter number
        chapter_match = re.search(r'\d+', chapter_title)
        if chapter_match:
            sanitized_chapter = chapter_match.group(0)
        else:
            sanitized_chapter = "unknown"

        target_dir = self.download_root / sanitized_title / f"chapter_{sanitized_chapter}"

        if dry_run:
            print(f"[dry-run] Would create: {target_dir}")
            for idx, url in enumerate(image_urls, 1):
                print(f"[dry-run] {idx:02d} -> {url}")
            return target_dir

        target_dir.mkdir(parents=True, exist_ok=True)

        for idx, url in enumerate(image_urls, 1):
            ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
            file_path = target_dir / f"{idx:03d}{ext}"

            if file_path.exists():
                print(f"Skipping existing file: {file_path.name}")
                continue

            print(f"Downloading {idx:03d}/{len(image_urls)} -> {file_path.name}")

            def _make_request():
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                return resp

            img_resp = self._request_with_retry(_make_request)
            file_path.write_bytes(img_resp.content)

        return target_dir

    # 5. Main download method --------------------------------------------------
    def download_chapter(
        self,
        manga_title: str,
        chapter_number: str,
        source: str,
        dry_run: bool = False,
        alternative_titles: Optional[List[str]] = None
    ) -> Dict:
        """
        Main method: Download a specific chapter

        Args:
            manga_title: Name of the manga
            chapter_number: Chapter number or label
            source: Source identifier (e.g., 'mangahere', 'mangafox')
            dry_run: Preview without downloading
            alternative_titles: List of alternative manga titles to try if main title fails

        Returns:
            Dict with success status, images downloaded, folder path, etc.
        """
        try:
            # Build list of titles to try (main title + alternatives)
            titles_to_try = [manga_title]
            if alternative_titles:
                titles_to_try.extend(alternative_titles)

            chosen_manga = None

            # Try each title until we find a match
            for title in titles_to_try:
                print(f"[INFO] Searching for manga: {title}")
                chosen_manga = self.resolve_manga_id(title, source)
                if chosen_manga:
                    print(f"[INFO] Found manga using title: {title}")
                    break

            if not chosen_manga:
                tried_titles = ", ".join(titles_to_try)
                return {
                    "success": False,
                    "error": f"No manga results found for any title: {tried_titles}",
                    "available_chapters": None,
                    "images_downloaded": 0,
                    "folder_path": None
                }

            manga_id = chosen_manga["id"]
            manga_title_resolved = chosen_manga["title"]
            print(f"[INFO] Using manga: {manga_title_resolved} (ID: {manga_id})")

            # Fetch chapter list
            print("[INFO] Fetching chapter list...")
            chapters = self.fetch_chapters(manga_id, source)

            if not chapters:
                return {
                    "success": False,
                    "error": "Could not fetch any chapters for this manga.",
                    "available_chapters": None,
                    "images_downloaded": 0,
                    "folder_path": None
                }

            # Resolve chapter
            chosen_chapter = self.resolve_chapter(chapters, chapter_number)
            if not chosen_chapter:
                available_chapters = [ch["title"] for ch in chapters[:20]]
                return {
                    "success": False,
                    "error": f"Chapter {chapter_number} not found.",
                    "available_chapters": available_chapters,
                    "images_downloaded": 0,
                    "folder_path": None
                }

            chapter_id = chosen_chapter["id"]
            chapter_title = chosen_chapter["title"]
            print(f"[INFO] Resolved chapter: {chapter_title}")

            if dry_run:
                return {
                    "success": True,
                    "error": None,
                    "available_chapters": None,
                    "images_downloaded": 0,
                    "folder_path": f"[DRY RUN] Would download: {manga_title_resolved}/{chapter_title}",
                    "chapter_title": chapter_title
                }

            # Queue download via Haruneko download API
            print("[INFO] Queueing download...")
            download_result = self.queue_download(
                manga_id=manga_id,
                chapter_id=chapter_id,
                source=source
            )

            download_id = download_result.get('id')
            if not download_id:
                return {
                    "success": False,
                    "error": "Failed to queue download - no download ID returned",
                    "available_chapters": None,
                    "images_downloaded": 0,
                    "folder_path": None
                }

            print(f"[INFO] Download queued with ID: {download_id}")
            print("[INFO] Waiting for download to complete...")

            # Wait for download to complete
            wait_result = self.wait_for_download(download_id)

            if not wait_result["success"]:
                return {
                    "success": False,
                    "error": wait_result["error"],
                    "available_chapters": None,
                    "images_downloaded": 0,
                    "folder_path": None,
                    "download_id": download_id,
                    "status": wait_result.get("status")
                }

            # Download completed successfully
            file_path = wait_result.get("file_path", "unknown")
            print(f"[SUCCESS] Download completed: {file_path}")

            return {
                "success": True,
                "error": None,
                "available_chapters": None,
                "images_downloaded": wait_result.get("data", {}).get("pageCount", 0),
                "folder_path": file_path,
                "download_id": download_id,
                "chapter_title": chapter_title
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "available_chapters": None,
                "images_downloaded": 0,
                "folder_path": None
            }

    def validate_manga_has_chapters(
        self,
        manga_title: str,
        chapter_numbers: List[int],
        source: str
    ) -> Dict:
        """
        Validate that a manga has ALL the required chapters

        Args:
            manga_title: Name of the manga
            chapter_numbers: List of chapter numbers to validate
            source: Source identifier

        Returns:
            Dict with success, manga_id, manga_title, and missing_chapters
        """
        try:
            # Search for manga (exact match only)
            chosen_manga = self.resolve_manga_id(manga_title, source)
            if not chosen_manga:
                return {
                    "success": False,
                    "manga_id": None,
                    "manga_title": None,
                    "missing_chapters": chapter_numbers,
                    "error": f"Manga '{manga_title}' not found (exact match required)"
                }

            manga_id = chosen_manga["id"]
            manga_title_resolved = chosen_manga["title"]

            # Fetch chapter list
            chapters = self.fetch_chapters(manga_id, source)

            if not chapters:
                return {
                    "success": False,
                    "manga_id": manga_id,
                    "manga_title": manga_title_resolved,
                    "missing_chapters": chapter_numbers,
                    "error": "Could not fetch any chapters for this manga"
                }

            # Check which chapters are missing
            missing_chapters = []
            for chapter_num in chapter_numbers:
                chapter_found = self.resolve_chapter(chapters, str(chapter_num))
                if not chapter_found:
                    missing_chapters.append(chapter_num)

            if missing_chapters:
                return {
                    "success": False,
                    "manga_id": manga_id,
                    "manga_title": manga_title_resolved,
                    "missing_chapters": missing_chapters,
                    "error": f"Missing chapters: {missing_chapters}"
                }

            # All chapters found!
            return {
                "success": True,
                "manga_id": manga_id,
                "manga_title": manga_title_resolved,
                "missing_chapters": [],
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "manga_id": None,
                "manga_title": None,
                "missing_chapters": chapter_numbers,
                "error": str(e)
            }

    def download_chapters(
        self,
        manga_title: str,
        chapter_numbers: List[int],
        source: str,
        dry_run: bool = False,
        alternative_titles: Optional[List[str]] = None,
        validate_first: bool = True
    ) -> Dict:
        """
        Download multiple chapters with validation

        Args:
            manga_title: Name of the manga
            chapter_numbers: List of chapter numbers to download
            source: Source identifier (e.g., 'mangahere', 'mangafox')
            dry_run: Preview without downloading
            alternative_titles: List of alternative manga titles to try if main title fails
            validate_first: Validate all chapters exist before downloading (default: True)

        Returns:
            Dict with success status, chapters downloaded, failed chapters, etc.
        """
        results = {
            "success": False,
            "manga_title": None,
            "total_chapters": len(chapter_numbers),
            "successful_downloads": 0,
            "failed_downloads": 0,
            "downloaded_chapters": [],
            "failed_chapters": [],
            "missing_chapters": [],
            "error": None
        }

        try:
            # Build list of titles to try (main title + alternatives)
            titles_to_try = [manga_title]
            if alternative_titles:
                titles_to_try.extend(alternative_titles)

            chosen_manga = None

            # Try each title until we find a match
            for title in titles_to_try:
                print(f"[INFO] Searching for manga: {title}")
                chosen_manga = self.resolve_manga_id(title, source)
                if chosen_manga:
                    print(f"[INFO] Found manga using title: {title}")
                    break

            if not chosen_manga:
                tried_titles = ", ".join(titles_to_try)
                results["error"] = f"No manga results found for any title: {tried_titles}"
                return results

            manga_id = chosen_manga["id"]
            manga_title_resolved = chosen_manga["title"]
            results["manga_title"] = manga_title_resolved
            print(f"[INFO] Using manga: {manga_title_resolved} (ID: {manga_id})")

            # Validate chapters exist first (if requested)
            if validate_first:
                print(f"[INFO] Validating {len(chapter_numbers)} chapters exist...")
                validation = self.validate_manga_has_chapters(
                    manga_title_resolved,
                    chapter_numbers,
                    source
                )

                if not validation["success"]:
                    results["missing_chapters"] = validation["missing_chapters"]
                    results["error"] = validation["error"]
                    print(f"[ERROR] Validation failed: {validation['error']}")
                    return results

                print("[INFO] All chapters validated successfully")

            # Fetch chapter list once
            print("[INFO] Fetching chapter list...")
            chapters = self.fetch_chapters(manga_id, source)

            if not chapters:
                results["error"] = "Could not fetch any chapters for this manga."
                return results

            # Download each chapter
            print(f"\n[INFO] Downloading {len(chapter_numbers)} chapters...")
            for idx, chapter_num in enumerate(chapter_numbers, 1):
                print(f"\n{'='*70}")
                print(f"[{idx}/{len(chapter_numbers)}] Processing Chapter {chapter_num}")
                print(f"{'='*70}")

                try:
                    # Resolve chapter
                    chosen_chapter = self.resolve_chapter(chapters, str(chapter_num))
                    if not chosen_chapter:
                        error_msg = f"Chapter {chapter_num} not found"
                        print(f"[ERROR] {error_msg}")
                        results["failed_chapters"].append({
                            "chapter_number": chapter_num,
                            "error": error_msg
                        })
                        results["failed_downloads"] += 1
                        continue

                    chapter_id = chosen_chapter["id"]
                    chapter_title = chosen_chapter["title"]
                    print(f"[INFO] Resolved chapter: {chapter_title}")

                    if dry_run:
                        print(f"[DRY RUN] Would download: {chapter_title}")
                        results["downloaded_chapters"].append({
                            "chapter_number": chapter_num,
                            "chapter_title": chapter_title,
                            "images_downloaded": 0,
                            "folder_path": f"[DRY RUN] {manga_title_resolved}/{chapter_title}"
                        })
                        results["successful_downloads"] += 1
                        continue

                    # Queue download via Haruneko download API
                    print("[INFO] Queueing download...")
                    download_result = self.queue_download(
                        manga_id=manga_id,
                        chapter_id=chapter_id,
                        source=source
                    )

                    download_id = download_result.get('id')
                    if not download_id:
                        error_msg = "Failed to queue download - no download ID returned"
                        print(f"[ERROR] {error_msg}")
                        results["failed_chapters"].append({
                            "chapter_number": chapter_num,
                            "error": error_msg
                        })
                        results["failed_downloads"] += 1
                        continue

                    print(f"[INFO] Download queued with ID: {download_id}")
                    print("[INFO] Waiting for download to complete...")

                    # Wait for download to complete
                    wait_result = self.wait_for_download(download_id)

                    if not wait_result["success"]:
                        error_msg = wait_result["error"]
                        print(f"[ERROR] {error_msg}")
                        results["failed_chapters"].append({
                            "chapter_number": chapter_num,
                            "error": error_msg,
                            "download_id": download_id
                        })
                        results["failed_downloads"] += 1
                        continue

                    # Download completed successfully
                    file_path = wait_result.get("file_path", "unknown")
                    page_count = wait_result.get("data", {}).get("pageCount", 0)
                    print(f"[SUCCESS] Download completed: {file_path}")

                    # Record success
                    results["downloaded_chapters"].append({
                        "chapter_number": chapter_num,
                        "chapter_title": chapter_title,
                        "images_downloaded": page_count,
                        "folder_path": file_path,
                        "download_id": download_id
                    })
                    results["successful_downloads"] += 1

                except Exception as e:
                    error_msg = str(e)
                    print(f"[ERROR] Failed to download chapter {chapter_num}: {error_msg}")
                    results["failed_chapters"].append({
                        "chapter_number": chapter_num,
                        "error": error_msg
                    })
                    results["failed_downloads"] += 1

            # Determine overall success
            if results["successful_downloads"] == len(chapter_numbers):
                results["success"] = True
                print(f"\n[SUCCESS] All {len(chapter_numbers)} chapters downloaded successfully!")
            elif results["successful_downloads"] > 0:
                results["success"] = True  # Partial success
                results["error"] = f"Partial success: {results['failed_downloads']} chapters failed"
                print(f"\n[WARNING] Partial success: {results['successful_downloads']}/{len(chapter_numbers)} chapters downloaded")
            else:
                results["error"] = "All chapter downloads failed"
                print(f"\n[ERROR] All chapter downloads failed")

            return results

        except Exception as e:
            results["error"] = str(e)
            print(f"[ERROR] Download batch failed: {str(e)}")
            return results


def main():
    """Example usage"""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Download manga chapters via Haruneko API"
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:3000",
        help="Haruneko API base URL (default: http://localhost:3000)"
    )
    parser.add_argument(
        "--source",
        type=str,
        required=True,
        help="Manga source (e.g., mangahere, mangafox)"
    )
    parser.add_argument(
        "--manga",
        type=str,
        required=True,
        help="Manga title"
    )
    parser.add_argument(
        "--chapters",
        type=str,
        required=True,
        help="Chapter numbers (comma-separated list, e.g., '1,2,3' or single chapter '1')"
    )
    parser.add_argument(
        "--download-dir",
        type=str,
        default="downloads",
        help="Download directory (default: downloads)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without downloading"
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip validation step (not recommended)"
    )

    args = parser.parse_args()

    # Parse chapter numbers
    chapter_str = args.chapters.strip()
    if ',' in chapter_str:
        # Multiple chapters
        chapter_numbers = [int(ch.strip()) for ch in chapter_str.split(',')]
    else:
        # Single chapter
        chapter_numbers = [int(chapter_str)]

    # Create service
    service = HarunekoMangaService(
        base_url=args.url,
        download_root=args.download_dir
    )

    # Download chapters
    if len(chapter_numbers) == 1:
        # Single chapter download
        print(f"[INFO] Downloading single chapter: {chapter_numbers[0]}")
        result = service.download_chapter(
            manga_title=args.manga,
            chapter_number=str(chapter_numbers[0]),
            source=args.source,
            dry_run=args.dry_run
        )

        # Print result
        print("\n" + "="*70)
        print("DOWNLOAD RESULT")
        print("="*70)
        print(json.dumps(result, indent=2))

        if result["success"]:
            print(f"\n✓ Successfully downloaded {result['images_downloaded']} images")
            print(f"  Location: {result['folder_path']}")
        else:
            print(f"\n✗ Download failed: {result['error']}")
            if result.get("available_chapters"):
                print(f"\nAvailable chapters:")
                for ch in result["available_chapters"]:
                    print(f"  - {ch}")
    else:
        # Multiple chapters download
        print(f"[INFO] Downloading {len(chapter_numbers)} chapters: {chapter_numbers}")
        result = service.download_chapters(
            manga_title=args.manga,
            chapter_numbers=chapter_numbers,
            source=args.source,
            dry_run=args.dry_run,
            validate_first=not args.no_validate
        )

        # Print result
        print("\n" + "="*70)
        print("BATCH DOWNLOAD RESULT")
        print("="*70)
        print(json.dumps(result, indent=2))

        if result["success"]:
            print(f"\n✓ Successfully downloaded {result['successful_downloads']}/{result['total_chapters']} chapters")
            if result.get("failed_downloads", 0) > 0:
                print(f"\n⚠ Failed chapters: {result['failed_downloads']}")
                for failed in result.get("failed_chapters", []):
                    print(f"  - Chapter {failed['chapter_number']}: {failed['error']}")
        else:
            print(f"\n✗ Download failed: {result['error']}")
            if result.get("missing_chapters"):
                print(f"\nMissing chapters: {result['missing_chapters']}")


if __name__ == "__main__":
    main()
