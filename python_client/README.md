# HaruNeko Python Client

**Simple Python client for downloading manga via the HaruNeko API**

Just provide a manga name and chapter numbers - the client handles everything else!

## Prerequisites

**⚠️ IMPORTANT: Start the HaruNeko API server first!**

```bash
# Navigate to haruneko project root
cd /path/to/haruneko

# Install dependencies (first time only)
npm install

# Build (first time only)
npm run build

# Start the server
npm run dev
```

Verify it's running: http://localhost:3000/api-docs

## Installation

```bash
cd python_client
pip install -r requirements.txt
```

## Quick Start

### Simplest Usage

```python
from haruneko_download_service import HaruNekoDownloadService

service = HaruNekoDownloadService()

# Just provide manga name and chapter numbers!
result = service.download_manga_chapters(
    source_id="mangahere",
    manga_name="One Piece",
    chapter_numbers=[1, 2, 3]
)

if result["success"]:
    download_id = result["download"]["response"]["data"]["id"]
    print(f"Download ID: {download_id}")
```

That's it! The service automatically:
1. Searches for the manga
2. Finds the best match
3. Gets all chapters
4. Matches your chapter numbers to actual chapter IDs
5. Initiates the download

### Validate Before Downloading

Check if manga and chapters exist without downloading:

```python
result = service.download_manga_chapters(
    source_id="mangahere",
    manga_name="Berserk",
    chapter_numbers=[1, 2, 3],
    validate_only=True  # Just check, don't download
)

if result["success"]:
    print(f"Found: {result['manga']['title']}")
    print(f"Chapters available: {len(result['chapters_found'])}")
else:
    print(f"Error: {result['error']}")
    print(f"Missing chapters: {result['chapters_missing']}")
```

### Custom Download Options

```python
result = service.download_manga_chapters(
    source_id="mangahere",
    manga_name="Naruto",
    chapter_numbers=[1, 2, 3, 4, 5],
    format="cbz",  # or "pdf", "epub", "images"
    options={
        "quality": "high",  # "low", "medium", or "high"
        "includeMetadata": True
    }
)
```

### Fractional Chapters

Works with decimal chapter numbers too:

```python
result = service.download_manga_chapters(
    source_id="mangahere",
    manga_name="One Piece",
    chapter_numbers=[1, 1.5, 2, 2.5, 3]  # Supports .5 chapters
)
```

## API Reference

### `download_manga_chapters()`

Main method for downloading manga chapters.

**Parameters:**
- `source_id` (str): Source identifier (e.g., "mangahere", "mangahere")
- `manga_name` (str): Name of the manga to download
- `chapter_numbers` (List[int|float|str]): Chapter numbers to download
- `format` (str, optional): Download format - "cbz", "pdf", "epub", or "images" (default: "cbz")
- `options` (dict, optional): Download options (quality, includeMetadata)
- `validate_only` (bool, optional): If True, only validate without downloading (default: False)

**Returns:**
```python
{
    "success": bool,
    "error": str or None,
    "manga": {
        "id": str,
        "title": str,
        "sourceId": str
    },
    "chapters_found": [...],  # List of matched chapter objects
    "chapters_missing": [...],  # List of chapter numbers not found
    "download": {
        "success": bool,
        "response": {...},  # API response with download ID
        "status_code": int
    }
}
```

## Examples

### Example 1: Validate First, Then Download

```python
from haruneko_download_service import HaruNekoDownloadService

service = HaruNekoDownloadService()

# Step 1: Validate
result = service.download_manga_chapters(
    source_id="mangahere",
    manga_name="Attack on Titan",
    chapter_numbers=[1, 2, 3, 4, 5],
    validate_only=True
)

if not result["success"]:
    print(f"Validation failed: {result['error']}")
    exit(1)

print(f"✓ Found: {result['manga']['title']}")
print(f"✓ All {len(result['chapters_found'])} chapters available")

# Step 2: Download
result = service.download_manga_chapters(
    source_id="mangahere",
    manga_name="Attack on Titan",
    chapter_numbers=[1, 2, 3, 4, 5],
    format="cbz"
)

if result["success"]:
    download_id = result["download"]["response"]["data"]["id"]
    print(f"✓ Download started! ID: {download_id}")
```

### Example 2: Error Handling

```python
result = service.download_manga_chapters(
    source_id="mangahere",
    manga_name="Non-Existent Manga",
    chapter_numbers=[1, 2, 3],
    validate_only=True
)

if not result["success"]:
    print(f"Error: {result['error']}")

    if result["chapters_missing"]:
        print(f"Missing chapters: {result['chapters_missing']}")
```

## ⚠️ Important: Downloads are Asynchronous!

The HaruNeko API processes downloads in the **background**:

1. `download_manga_chapters()` returns a download ID **immediately**
2. The download processes asynchronously on the server
3. You must **poll** the status endpoint to check progress
4. When `status == 'completed'`, you can download the file

### Complete Download Workflow with Polling

```python
import time
import requests
from haruneko_download_service import HaruNekoDownloadService

service = HaruNekoDownloadService()

# Step 1: Initiate download
result = service.download_manga_chapters(
    source_id="mangahere",
    manga_name="One Piece",
    chapter_numbers=[1],
    format="cbz"
)

if not result["success"]:
    print(f"Failed: {result['error']}")
    exit(1)

download_id = result["download"]["response"]["data"]["id"]
print(f"Download initiated! ID: {download_id}")

# Step 2: Poll for completion
base_url = "http://localhost:3000/api/v1"

while True:
    response = requests.get(f"{base_url}/downloads/{download_id}")
    data = response.json()["data"]

    status = data["status"]
    progress = data.get("progress", 0)

    print(f"\rStatus: {status} | Progress: {progress:.1f}%", end="", flush=True)

    if status == "completed":
        file_url = data["fileUrl"]
        print(f"\n✓ Download complete!")
        print(f"File URL: http://localhost:3000{file_url}")
        break
    elif status == "failed":
        print(f"\n✗ Download failed: {data.get('error')}")
        break

    time.sleep(2)  # Wait 2 seconds before next poll
```

### Quick Status Check

```bash
# Check status
curl http://localhost:3000/api/v1/downloads/{download_id}

# Download completed file (only when status is 'completed')
curl http://localhost:3000/api/v1/downloads/{download_id}/file -o manga.cbz
```

**Note:** If you try to download the file before it's completed, you'll get:
```json
{"success": false, "error": {"message": "Download is not completed yet"}}
```

## How It Works

### Chapter Matching

The service uses multiple strategies to match your chapter numbers:

1. **Direct number match**: Matches chapter `number` field (e.g., chapter 1 → `{"number": 1}`)
2. **Title extraction**: Extracts numbers from titles (e.g., "Chapter 1" → 1)
3. **Decimal support**: Handles fractional chapters (e.g., 1.5, 2.5)
4. **String matching**: For non-numeric identifiers (e.g., "Prologue", "Epilogue")

### Manga Matching

The service finds manga using:

1. **Exact match**: Case-insensitive exact title match
2. **Normalized match**: Ignores punctuation and extra spaces
3. **Fallback**: Uses first search result if no exact match

## Available Sources

HaruNeko supports 788+ manga sources! Common ones:
- mangahere
- mangahere
- mangakakalot
- manganato
- mangapark
- asurascans
- And 780+ more!

List all sources:
```bash
curl http://localhost:3000/api/v1/sources?limit=1000
```

## Testing

Run the simple test suite:

```bash
# Make sure API server is running!
python test_simple.py
```

Or run an example:

```bash
python simple_example.py
```

## Troubleshooting

### Connection Refused
```
ConnectionError: [Errno 111] Connection refused
```

**Solution:** Start the API server first!
```bash
cd /path/to/haruneko && npm run dev
```

### Manga Not Found

**Solution:** Try different spellings or check the source:
```python
# Try variations
service.download_manga_chapters("mangahere", "One Piece", [1])
service.download_manga_chapters("mangahere", "One-Piece", [1])
service.download_manga_chapters("mangahere", "OnePiece", [1])
```

### Chapters Not Found

**Solution:** Validate first to see what's available:
```python
result = service.download_manga_chapters(
    "mangahere", "One Piece", [1, 2, 3],
    validate_only=True
)
print(f"Chapters found: {[ch['title'] for ch in result['chapters_found']]}")
```

## Rate Limiting

The client automatically handles rate limiting:
- Max retries: 10
- Initial delay: 3 seconds
- Exponential backoff: 3s → 6s → 12s → 24s → ...

## Requirements

- Python 3.7+
- requests >= 2.31.0
- HaruNeko API server running at http://localhost:3000

## License

Same as HaruNeko project (Unlicense)
