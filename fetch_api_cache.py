#!/usr/bin/env python3
"""
Fetch Bible catalog data from Digital Bible Platform API.

This script downloads the complete Bible catalog and saves it to the api-cache/ directory.
The cached data is then used by sort_cache_data.py to organize metadata.

Usage:
    python3 fetch_api_cache.py

Output:
    api-cache/
    ├── bibles/
    │   ├── bibles_page_1.json
    │   ├── bibles_page_2.json
    │   └── ...
    └── samples/
        ├── languages.json
        ├── countries.json
        ├── audio_timestamps_filesets.json
        └── ...

Requirements:
    - Set DBP_API_KEY environment variable
    - Internet connection
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("Error: Required packages not installed.")
    print("Please run: pip install requests python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv()

# API Configuration
API_KEY = os.getenv("DBP_API_KEY") or os.getenv("BIBLE_API_KEY")
API_BASE_URL = "https://4.dbt.io/api"
API_TIMEOUT = 30

# Output directories
CACHE_DIR = Path("api-cache")
BIBLES_DIR = CACHE_DIR / "bibles"
SAMPLES_DIR = CACHE_DIR / "samples"


def log(message, level="INFO"):
    """Print log message."""
    prefix = {
        "INFO": "ℹ",
        "SUCCESS": "✓",
        "WARNING": "⚠",
        "ERROR": "✗",
    }.get(level, "ℹ")
    print(f"{prefix} {message}")


def check_api_key():
    """Check if API key is set."""
    if not API_KEY:
        log("API key not found!", "ERROR")
        log("Set DBP_API_KEY environment variable:", "ERROR")
        log("  export DBP_API_KEY='your-api-key-here'", "ERROR")
        log("", "ERROR")
        log("Get your API key from: https://www.biblebrain.com/", "INFO")
        sys.exit(1)
    log(f"API key found: {API_KEY[:10]}...", "SUCCESS")


def make_api_request(endpoint, params=None):
    """Make API request with error handling."""
    if params is None:
        params = {}

    params["key"] = API_KEY
    params["v"] = "4"

    url = f"{API_BASE_URL}/{endpoint}"

    try:
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log(f"API request failed: {e}", "ERROR")
        return None


def fetch_paginated_bibles():
    """Fetch all Bible catalog pages."""
    log("Fetching Bible catalog (paginated)...", "INFO")

    BIBLES_DIR.mkdir(parents=True, exist_ok=True)

    page = 1
    total_bibles = 0

    while True:
        log(f"  Fetching page {page}...", "INFO")

        data = make_api_request("bibles", {"page": page, "limit": 200})

        if not data or "data" not in data:
            log(f"No more data at page {page}", "WARNING")
            break

        # Save page
        page_file = BIBLES_DIR / f"bibles_page_{page}.json"
        with open(page_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        bibles_in_page = len(data.get("data", []))
        total_bibles += bibles_in_page

        log(f"  ✓ Saved page {page} ({bibles_in_page} Bibles)", "SUCCESS")

        # Check if there are more pages
        meta = data.get("meta", {})
        pagination = meta.get("pagination", {})

        if not pagination.get("next_page_url"):
            log("Reached last page", "INFO")
            break

        page += 1
        time.sleep(0.5)  # Rate limiting

    log(f"Total Bibles fetched: {total_bibles}", "SUCCESS")
    return total_bibles


def fetch_sample_data():
    """Fetch sample API responses."""
    log("Fetching sample data...", "INFO")

    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    samples = [
        ("languages", "languages", {}),
        ("countries", "countries", {}),
        ("alphabets", "alphabets", {}),
        ("bibles_single", "bibles", {"limit": 1}),
        ("languages_single", "languages", {"iso": "eng"}),
        ("bible_ENGESV", "bibles/ENGESV", {}),
        ("fileset_media_types", "bibles/filesets/media/types", {}),
    ]

    for name, endpoint, params in samples:
        log(f"  Fetching {name}...", "INFO")

        data = make_api_request(endpoint, params)

        if data:
            output_file = SAMPLES_DIR / f"{name}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            log(f"  ✓ Saved {name}.json", "SUCCESS")
        else:
            log(f"  Failed to fetch {name}", "WARNING")

        time.sleep(0.3)  # Rate limiting


def fetch_timing_filesets():
    """Fetch list of filesets with timing data."""
    log("Fetching timing filesets...", "INFO")

    # This requires fetching all bibles and filtering for timing
    # We'll create a list by scanning the cached bible pages

    timing_filesets = []

    if not BIBLES_DIR.exists():
        log("Bible pages not yet fetched", "WARNING")
        return

    bible_files = sorted(BIBLES_DIR.glob("bibles_page_*.json"))

    for bible_file in bible_files:
        with open(bible_file) as f:
            data = json.load(f)

        for bible in data.get("data", []):
            filesets = bible.get("filesets", {})

            for platform, fileset_list in filesets.items():
                for fileset in fileset_list:
                    # Check if fileset has timing data
                    if (
                        "timing_est_err" in fileset
                        or "timing" in fileset.get("id", "").lower()
                    ):
                        timing_filesets.append(
                            {
                                "fileset_id": fileset.get("id"),
                                "bible_abbr": bible.get("abbr"),
                                "language_iso": bible.get("iso"),
                                "timing_type": fileset.get("timing_est_err", "unknown"),
                            }
                        )

    # Save timing filesets
    output_file = SAMPLES_DIR / "audio_timestamps_filesets.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(timing_filesets, f, indent=2, ensure_ascii=False)

    log(f"Found {len(timing_filesets)} filesets with timing data", "SUCCESS")


def create_readme():
    """Create README for api-cache directory."""
    readme_content = """# API Cache

Cached responses from the Digital Bible Platform API.

## Structure

```
api-cache/
├── bibles/              # Complete Bible catalog (paginated)
│   ├── bibles_page_1.json
│   ├── bibles_page_2.json
│   └── ...
└── samples/             # Sample API responses
    ├── languages.json
    ├── countries.json
    ├── audio_timestamps_filesets.json
    └── ...
```

## Usage

These cached files are used by `sort_cache_data.py` to organize metadata into the `sorted/` directory.

## Updating the Cache

To refresh the cached data:

```bash
python3 fetch_api_cache.py
```

## API Information

- **API**: Digital Bible Platform v4
- **URL**: https://4.dbt.io/api
- **Documentation**: https://www.biblebrain.com/
- **Provider**: Faith Comes By Hearing

## Last Updated

Run `fetch_api_cache.py` to update this cache with the latest data from the API.
"""

    readme_file = CACHE_DIR / "README.md"
    with open(readme_file, "w") as f:
        f.write(readme_content)

    log("Created README.md", "SUCCESS")


def main():
    """Main entry point."""
    print("=" * 70)
    print("Digital Bible Platform - API Cache Fetcher")
    print("=" * 70)
    print()

    # Check API key
    check_api_key()
    print()

    # Create directories
    CACHE_DIR.mkdir(exist_ok=True)
    BIBLES_DIR.mkdir(exist_ok=True)
    SAMPLES_DIR.mkdir(exist_ok=True)

    # Fetch data
    try:
        # Fetch paginated Bible catalog
        total_bibles = fetch_paginated_bibles()
        print()

        # Fetch sample data
        fetch_sample_data()
        print()

        # Extract timing filesets
        fetch_timing_filesets()
        print()

        # Create README
        create_readme()
        print()

        # Summary
        print("=" * 70)
        print("✓ Cache fetch complete!")
        print("=" * 70)
        print(f"Total Bibles: {total_bibles}")
        print(f"Output directory: {CACHE_DIR}")
        print()
        print("Next steps:")
        print("  1. Run: python3 sort_cache_data.py")
        print("  2. Run: python3 download_language_content.py <iso> --books <books>")
        print("=" * 70)

    except KeyboardInterrupt:
        print()
        log("Interrupted by user", "WARNING")
        sys.exit(1)
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
