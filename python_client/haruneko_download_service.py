"""
HaruNeko Download Service - Download manga chapters via HaruNeko API

Simple interface:
    service = HaruNekoDownloadService()
    service.download_manga_chapters(
        source_id="mangahere",
        manga_name="berserk",
        chapter_numbers=[1, 2, 3]
    )
"""
import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import requests


class HaruNekoDownloadService:
    """Service for downloading manga chapters via HaruNeko API"""

    def __init__(
        self,
        base_url: str = "http://localhost:3000/api/v1",
        download_root: str = "downloads",
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.download_root = Path(download_root)
        self.download_root.mkdir(parents=True, exist_ok=True)

        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
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
                        print(
                            f"[WARN] 429 Too Many Requests - Retrying in {delay}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(delay)
                        delay *= 2  # Double the delay for next retry
                    else:
                        print(
                            f"[ERROR] 429 Too Many Requests - "
                            f"Max retries ({max_retries}) exceeded"
                        )
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

    # ========================================================================
    # SIMPLIFIED API - Main methods you should use
    # ========================================================================

    def download_manga_chapters(
        self,
        source_id: str,
        manga_name: str,
        chapter_numbers: List[Union[int, float, str]],
        format: str = "cbz",
        options: Optional[Dict[str, Any]] = None,
        validate_only: bool = False
    ) -> Dict:
        """
        Main method: Search for manga, find chapters, and download them

        Args:
            source_id: Source ID (e.g., "mangahere", "mangadex")
            manga_name: Name of the manga to search for
            chapter_numbers: List of chapter numbers to download (e.g., [1, 2, 3] or ["1", "2.5", "3"])
            format: Download format (default: "cbz")
            options: Download options (quality, includeMetadata)
            validate_only: If True, only validate without downloading

        Returns:
            Dict with success status, manga info, and download results

        Example:
            result = service.download_manga_chapters(
                source_id="mangahere",
                manga_name="berserk",
                chapter_numbers=[1, 2, 3]
            )
        """
        print(f"\n{'='*70}")
        print(f"  MANGA DOWNLOAD REQUEST")
        print(f"{'='*70}")
        print(f"Source: {source_id}")
        print(f"Manga: {manga_name}")
        print(f"Chapters: {chapter_numbers}")
        print(f"{'='*70}\n")

        # Step 1: Search for manga
        print(f"[1/4] Searching for '{manga_name}'...")
        manga = self._find_manga(source_id, manga_name)

        if not manga:
            return {
                "success": False,
                "error": f"Manga '{manga_name}' not found on source '{source_id}'",
                "manga": None,
                "chapters_found": [],
                "chapters_missing": chapter_numbers,
                "download": None
            }

        manga_id = manga["id"]
        manga_title = manga.get("title", "Unknown")
        print(f"✓ Found: {manga_title}")
        print(f"  Manga ID: {manga_id[:80]}...")

        # Step 2: Get all chapters
        print(f"\n[2/4] Fetching chapters...")
        all_chapters = self._get_chapters(source_id, manga_id)

        if not all_chapters:
            return {
                "success": False,
                "error": f"No chapters found for '{manga_title}'",
                "manga": manga,
                "chapters_found": [],
                "chapters_missing": chapter_numbers,
                "download": None
            }

        print(f"✓ Found {len(all_chapters)} total chapters")

        # Step 3: Match requested chapters to actual chapter IDs
        print(f"\n[3/4] Matching requested chapters...")
        matched_chapters, missing_chapters = self._match_chapters(
            all_chapters,
            chapter_numbers
        )

        if missing_chapters:
            print(f"✗ Missing chapters: {missing_chapters}")
            return {
                "success": False,
                "error": f"Chapters not found: {missing_chapters}",
                "manga": manga,
                "chapters_found": matched_chapters,
                "chapters_missing": missing_chapters,
                "download": None
            }

        print(f"✓ All {len(matched_chapters)} chapters found!")
        for ch in matched_chapters:
            print(f"  - {ch.get('title', 'Unknown')} (ID: {ch['id'][:50]}...)")

        if validate_only:
            print(f"\n[INFO] Validation complete (validate_only=True)")
            return {
                "success": True,
                "error": None,
                "manga": manga,
                "chapters_found": matched_chapters,
                "chapters_missing": [],
                "download": None
            }

        # Step 4: Download
        print(f"\n[4/4] Initiating download...")
        chapter_ids = [ch["id"] for ch in matched_chapters]

        download_result = self._download_chapters(
            source_id,
            manga_id,
            chapter_ids,
            format,
            options
        )

        if download_result["success"]:
            print(f"✓ Download initiated successfully!")
            download_data = download_result.get("response", {}).get("data", {})
            download_id = download_data.get("id", "N/A")
            print(f"  Download ID: {download_id}")
            print(f"\n  Check status: GET /api/v1/downloads/{download_id}")
            print(f"  Get file: GET /api/v1/downloads/{download_id}/file")
        else:
            print(f"✗ Download failed: {download_result.get('error')}")

        return {
            "success": download_result["success"],
            "error": download_result.get("error"),
            "manga": manga,
            "chapters_found": matched_chapters,
            "chapters_missing": [],
            "download": download_result
        }

    # ========================================================================
    # INTERNAL HELPER METHODS
    # ========================================================================

    def _find_manga(self, source_id: str, manga_name: str) -> Optional[Dict]:
        """
        Search for manga and return best match

        Tries exact match first, then normalized match (case-insensitive, no punctuation)
        """
        try:
            # Search with the manga name - increase limit to get more results
            results = self._search_manga(source_id, manga_name, page=1, limit=100)

            if not results:
                return None

            # Strategy 1: Exact match (case-insensitive)
            manga_name_lower = manga_name.strip().lower()
            for manga in results:
                if manga.get("title", "").strip().lower() == manga_name_lower:
                    print(f"  Match type: Exact")
                    return manga

            # Strategy 2: Normalized match (remove punctuation, extra spaces)
            normalized_query = self._normalize_title(manga_name)
            for manga in results:
                if self._normalize_title(manga.get("title", "")) == normalized_query:
                    print(f"  Match type: Normalized (fuzzy)")
                    return manga

            # Strategy 3: Partial match - find best match that contains the query
            # Prioritize shorter titles (more likely to be the main series)
            partial_matches = []
            for manga in results:
                title_lower = manga.get("title", "").lower()
                if manga_name_lower in title_lower:
                    partial_matches.append((manga, len(manga.get("title", ""))))

            if partial_matches:
                # Sort by title length (shorter = better)
                partial_matches.sort(key=lambda x: x[1])
                best_match = partial_matches[0][0]
                print(f"  Match type: Partial (shortest match containing query)")
                print(f"  Selected: {best_match.get('title')}")
                return best_match

            # Strategy 4: Return first result as last resort
            print(f"  Match type: First result (no match found)")
            print(f"  WARNING: This might not be what you want!")
            return results[0]

        except Exception as e:
            print(f"[ERROR] Search failed: {e}")
            return None

    @staticmethod
    def _normalize_title(title: str) -> str:
        """
        Normalize title by removing punctuation and extra spaces
        Used for fuzzy matching

        Examples:
            "Berserk!" -> "berserk"
            "One-Punch Man" -> "onepunchman"
        """
        # Remove all punctuation and convert to lowercase
        normalized = re.sub(r'[^\w\s]', '', title.lower())
        # Remove extra whitespace
        normalized = re.sub(r'\s+', '', normalized)
        return normalized

    def _match_chapters(
        self,
        all_chapters: List[Dict],
        requested_numbers: List[Union[int, float, str]]
    ) -> tuple[List[Dict], List[Union[int, float, str]]]:
        """
        Match requested chapter numbers to actual chapter objects

        Returns:
            (matched_chapters, missing_chapters)
        """
        matched = []
        missing = []

        for requested_num in requested_numbers:
            # Normalize the requested number
            try:
                requested_float = float(requested_num)
            except (ValueError, TypeError):
                # If it's not a number, try string matching
                matched_chapter = self._find_chapter_by_string(all_chapters, str(requested_num))
                if matched_chapter:
                    matched.append(matched_chapter)
                else:
                    missing.append(requested_num)
                continue

            # Try to find chapter by number
            matched_chapter = None

            # Strategy 1: Match by chapter.number field (BEST)
            for chapter in all_chapters:
                chapter_number = chapter.get("number")
                if chapter_number is not None:
                    try:
                        if float(chapter_number) == requested_float:
                            matched_chapter = chapter
                            break
                    except (ValueError, TypeError):
                        pass

            # Strategy 2: Extract chapter number from title patterns
            # Only match chapter number patterns, not random numbers in descriptions
            if not matched_chapter:
                for chapter in all_chapters:
                    title = chapter.get("title", "")

                    # Try common chapter patterns:
                    # "Chapter 1", "Ch. 1", "Ch.828", "Episode 1", etc.
                    patterns = [
                        r'(?:Chapter|Ch\.?|Episode|Ep\.?)\s*(\d+(?:\.\d+)?)',  # "Chapter 1", "Ch.828"
                        r'^(\d+(?:\.\d+)?)\s*[-:]',  # "1 -", "1.5:"
                        r'^(\d+(?:\.\d+)?)\s*$',  # Just a number
                    ]

                    for pattern in patterns:
                        match = re.search(pattern, title, re.IGNORECASE)
                        if match:
                            try:
                                chapter_num = float(match.group(1))
                                if chapter_num == requested_float:
                                    matched_chapter = chapter
                                    break
                            except (ValueError, IndexError):
                                pass
                        if matched_chapter:
                            break

                    if matched_chapter:
                        break

            if matched_chapter:
                matched.append(matched_chapter)
            else:
                missing.append(requested_num)

        return matched, missing

    def _find_chapter_by_string(self, all_chapters: List[Dict], query: str) -> Optional[Dict]:
        """Find chapter by string matching (for non-numeric chapter identifiers)"""
        query_lower = query.lower().strip()

        # Try exact title match
        for chapter in all_chapters:
            if chapter.get("title", "").lower().strip() == query_lower:
                return chapter

        # Try partial match
        for chapter in all_chapters:
            if query_lower in chapter.get("title", "").lower():
                return chapter

        return None

    # ========================================================================
    # LOW-LEVEL API METHODS (you can use these directly if needed)
    # ========================================================================

    def _search_manga(
        self,
        source_id: str,
        query: str,
        page: int = 1,
        limit: int = 100
    ) -> List[Dict]:
        """
        Search for manga by title with retry logic for 429 errors
        """
        def _make_request():
            url = f"{self.base_url}/sources/{source_id}/search"
            params = {"page": page, "limit": limit, "q": query}
            resp = self.session.get(url, params=params, headers=self.headers, timeout=15)
            resp.raise_for_status()
            return resp

        resp = self._request_with_retry(_make_request)
        return resp.json().get("data", [])

    def _get_chapters(
        self,
        source_id: str,
        manga_id_raw: str,
        debug: bool = False
    ) -> List[Dict]:
        """
        Fetch all chapters for a manga
        """
        manga_id_encoded = urllib.parse.quote(manga_id_raw, safe="")

        def _make_request():
            url = f"{self.base_url}/sources/{source_id}/manga/{manga_id_encoded}/chapters"
            if debug:
                print(f"[DEBUG] Requesting: {url}")
            resp = self.session.get(url, headers=self.headers, timeout=15)
            resp.raise_for_status()
            return resp

        try:
            resp = self._request_with_retry(_make_request)
            data = resp.json()

            if debug:
                print(f"[DEBUG] Response status: {resp.status_code}")
                print(f"[DEBUG] Response success: {data.get('success')}")
                print(f"[DEBUG] Response data length: {len(data.get('data', []))}")
                if not data.get('success'):
                    print(f"[DEBUG] Response error: {data.get('error')}")

            # Check if API returned an error
            if not data.get("success", True):
                error_msg = data.get("error", {})
                print(f"[ERROR] API returned error: {error_msg}")
                return []

            return data.get("data", [])
        except requests.HTTPError as e:
            print(f"[ERROR] HTTP error fetching chapters: {e}")
            if debug and hasattr(e, 'response') and e.response is not None:
                print(f"[DEBUG] Response text: {e.response.text[:500]}")
            return []
        except Exception as e:
            print(f"[ERROR] Failed to fetch chapters: {type(e).__name__}: {e}")
            return []

    def _download_chapters(
        self,
        source_id: str,
        manga_id_raw: str,
        chapter_ids: List[str],
        format: str = "cbz",
        options: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """
        Download multiple chapters
        """
        if options is None:
            options = {
                "quality": "high",
                "includeMetadata": True,
            }

        payload = {
            "sourceId": source_id,
            "mangaId": manga_id_raw,
            "chapterIds": chapter_ids,
            "format": format,
            "options": options,
        }

        def _make_request():
            url = f"{self.base_url}/downloads"
            resp = self.session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            resp.raise_for_status()
            return resp

        try:
            resp = self._request_with_retry(_make_request)
            result = resp.json()

            return {
                "success": True,
                "error": None,
                "response": result,
                "status_code": resp.status_code
            }

        except requests.HTTPError as e:
            error_text = e.response.text if e.response else str(e)
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {error_text}",
                "response": None,
                "status_code": e.response.status_code if e.response else None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": None,
                "status_code": None
            }
