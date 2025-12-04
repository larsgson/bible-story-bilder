#!/usr/bin/env python3
"""
Script to download Bible text, audio, and timing files using sorted metadata.

This script uses ONLY the sorted/ directory for metadata and language information,
making API calls only to download actual content (audio files, text, timing data).

Key features:
- Single language download: python download_language_content.py <iso> --books <books>
- Batch download by category: python download_language_content.py --book-set <category>

Book-set categories:
- ALL: All available languages (default for batch)
- SYNC_FULL: Languages with syncable full Bible (OT+NT)
- SYNC_NT: Languages with syncable New Testament
- SYNC_OT: Languages with syncable Old Testament
- TIMING_FULL: Languages with timing data for full Bible
- TIMING_NT: Languages with timing data for New Testament
- TIMING_OT: Languages with timing data for Old Testament

Prerequisites:
    1. Generate sorted metadata first: python sort_cache_data.py
    2. Set BIBLE_API_KEY in .env file

Usage:
    # Single language
    python download_language_content.py eng --books GEN,EXO,MAT
    python download_language_content.py spa --books GEN:1-5

    # Batch by category
    python download_language_content.py --book-set SYNC_NT --books MAT:1
    python download_language_content.py --book-set TIMING_FULL --books PSA:117
    python download_language_content.py --book-set ALL --books GEN:1-3

Output files:
    downloads/BB/{iso}/{DISTINCT_ID}/{BOOK}/{BOOK}_{CHAPTER:03d}_{FULL_FILESET_ID}.{ext}
    - {iso} is language code (may have country suffix for duplicates)
    - {DISTINCT_ID} is shortened version ID (Bible abbreviation)
    - {BOOK} is 3-letter book code subdirectory
    - Filenames use full fileset ID with format suffixes

Metadata source:
    sorted/BB/{iso}/{FILESET_ID}/metadata.json

Requirements:
    pip install -r requirements.txt
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import requests
    from dotenv import load_dotenv
except ImportError as e:
    print("Error: Required packages not installed.")
    print("Please run: pip install -r requirements.txt")
    print(f"Missing module: {e.name}")
    sys.exit(1)

# Load environment variables from .env file
load_dotenv()

# API Configuration
BIBLE_API_KEY = os.getenv("BIBLE_API_KEY", "")
BIBLE_API_BASE_URL = "https://4.dbt.io/api"
API_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 60

# Directories
SORTED_DIR = Path("sorted/BB")  # Metadata source
OUTPUT_DIR = Path("downloads/BB")  # Content destination
DOWNLOAD_LOG_DIR = Path("download_log")
CONFIG_DIR = Path("config")
REGIONS_CONFIG = CONFIG_DIR / "regions.conf"
STORY_SET_CONFIG = CONFIG_DIR / "story-set.conf"

# Old Testament and New Testament book mappings
OT_BOOKS = {
    "GEN": 50,
    "EXO": 40,
    "LEV": 27,
    "NUM": 36,
    "DEU": 34,
    "JOS": 24,
    "JDG": 21,
    "RUT": 4,
    "1SA": 31,
    "2SA": 24,
    "1KI": 22,
    "2KI": 25,
    "1CH": 29,
    "2CH": 36,
    "EZR": 10,
    "NEH": 13,
    "EST": 10,
    "JOB": 42,
    "PSA": 150,
    "PRO": 31,
    "ECC": 12,
    "SNG": 8,
    "ISA": 66,
    "JER": 52,
    "LAM": 5,
    "EZK": 48,
    "DAN": 12,
    "HOS": 14,
    "JOL": 3,
    "AMO": 9,
    "OBA": 1,
    "JON": 4,
    "MIC": 7,
    "NAM": 3,
    "HAB": 3,
    "ZEP": 3,
    "HAG": 2,
    "ZEC": 14,
    "MAL": 4,
}

NT_BOOKS = {
    "MAT": 28,
    "MRK": 16,
    "LUK": 24,
    "JHN": 21,
    "ACT": 28,
    "ROM": 16,
    "1CO": 16,
    "2CO": 13,
    "GAL": 6,
    "EPH": 6,
    "PHP": 4,
    "COL": 4,
    "1TH": 5,
    "2TH": 3,
    "1TI": 6,
    "2TI": 4,
    "TIT": 3,
    "PHM": 1,
    "HEB": 13,
    "JAS": 5,
    "1PE": 5,
    "2PE": 3,
    "1JN": 5,
    "2JN": 1,
    "3JN": 1,
    "JUD": 1,
    "REV": 22,
}

ALL_BOOKS = {**OT_BOOKS, **NT_BOOKS}

# Error tracking
_ERROR_LOG = {}

# Exclusion tracking
_EXCLUSIONS = {
    "sa_versions": set(),
    "partial_content": set(),
    "story_adaptations": set(),
}


def load_exclusions():
    """Load exclusion data from sorted/BB/exclude_download.json."""
    global _EXCLUSIONS

    exclusion_file = SORTED_DIR / "exclude_download.json"
    if not exclusion_file.exists():
        return

    try:
        with open(exclusion_file) as f:
            data = json.load(f)

        # Load excluded fileset IDs into sets for fast lookup
        for item in data.get("exclusions", {}).get("sa_versions", []):
            _EXCLUSIONS["sa_versions"].add(item["fileset_id"])

        for item in data.get("exclusions", {}).get("partial_content", []):
            _EXCLUSIONS["partial_content"].add(item["fileset_id"])

        for item in data.get("exclusions", {}).get("story_adaptations", []):
            _EXCLUSIONS["story_adaptations"].add(item["fileset_id"])

        log(
            f"Loaded exclusions: {len(_EXCLUSIONS['sa_versions'])} SA (streaming-only), "
            f"{len(_EXCLUSIONS['story_adaptations'])} story adaptations",
            "INFO",
        )
    except Exception as e:
        log(f"Failed to load exclusions: {e}", "WARNING")


def log(message: str, level: str = "INFO"):
    """Print a log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def load_error_log(iso: str) -> Dict:
    """Load error log for a language."""
    error_file = DOWNLOAD_LOG_DIR / f"{iso}_errors.json"
    if error_file.exists():
        with open(error_file) as f:
            return json.load(f)
    return {"language": iso, "errors": []}


def save_error_log(iso: str, error_data: Dict):
    """Save error log for a language."""
    DOWNLOAD_LOG_DIR.mkdir(parents=True, exist_ok=True)
    error_file = DOWNLOAD_LOG_DIR / f"{iso}_errors.json"

    # Add timestamp to the error data structure
    error_data["last_updated"] = datetime.now().isoformat()

    with open(error_file, "w") as f:
        json.dump(error_data, f, indent=2, ensure_ascii=False)


def get_error_summary(iso: str) -> Dict:
    """Get summary of errors by content type.

    Returns:
        Dict with counts of errors by type
    """
    if iso not in _ERROR_LOG:
        return {
            "total_chapters_with_errors": 0,
            "audio_errors": 0,
            "text_errors": 0,
            "timing_errors": 0,
        }

    summary = {
        "total_chapters_with_errors": 0,
        "audio_errors": 0,
        "text_errors": 0,
        "timing_errors": 0,
    }

    for error_entry in _ERROR_LOG[iso]["errors"]:
        # Count chapters with any errors
        if (
            error_entry.get("audio_errors")
            or error_entry.get("text_errors")
            or error_entry.get("timing_errors")
        ):
            summary["total_chapters_with_errors"] += 1

        # Count errors by type
        summary["audio_errors"] += len(error_entry.get("audio_errors", []))
        summary["text_errors"] += len(error_entry.get("text_errors", []))
        summary["timing_errors"] += len(error_entry.get("timing_errors", []))

    return summary


def log_download_error(
    iso: str,
    book_id: str,
    chapter: int,
    content_type: str,  # 'audio', 'text', or 'timing'
    error_type: str,
    fileset: Optional[str] = None,
    distinct_id: Optional[str] = None,
    format_type: Optional[str] = None,
    details: Optional[str] = None,
):
    """Log a download error with detailed format information.

    Args:
        iso: Language ISO code
        book_id: Book identifier
        chapter: Chapter number
        content_type: Type of content ('audio', 'text', or 'timing')
        error_type: Type of error
        fileset: Fileset ID
        distinct_id: Distinct Bible version ID
        format_type: Format type (e.g., 'mp3', 'opus', 'mp3-stream')
        details: Additional error details
    """
    global _ERROR_LOG

    if iso not in _ERROR_LOG:
        _ERROR_LOG[iso] = load_error_log(iso)

    # Find or create error entry for this book/chapter
    error_entry = None
    for entry in _ERROR_LOG[iso]["errors"]:
        if entry["book"] == book_id and entry["chapter"] == chapter:
            error_entry = entry
            break

    if error_entry is None:
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "book": book_id,
            "chapter": chapter,
            "audio_errors": [],
            "text_errors": [],
            "timing_errors": [],
        }
        _ERROR_LOG[iso]["errors"].append(error_entry)

    # Create the format-specific error
    format_error = {
        "timestamp": datetime.now().isoformat(),
        "error_type": error_type,
    }

    if fileset:
        format_error["fileset"] = fileset
    if distinct_id:
        format_error["distinct_id"] = distinct_id
    if format_type:
        format_error["format"] = format_type
    if details:
        format_error["details"] = details

    # Add to appropriate error list
    if content_type == "audio":
        error_entry["audio_errors"].append(format_error)
    elif content_type == "text":
        error_entry["text_errors"].append(format_error)
    elif content_type == "timing":
        error_entry["timing_errors"].append(format_error)

    # Update timestamp
    error_entry["timestamp"] = datetime.now().isoformat()

    save_error_log(iso, _ERROR_LOG[iso])


def load_language_metadata(iso: str) -> Dict[str, Dict]:
    """Load all metadata for a language from sorted/BB directory.

    Reads metadata.json files from sorted/BB/{iso}/{fileset_id}/ structure.
    """
    lang_dir = SORTED_DIR / iso
    if not lang_dir.exists():
        return {}

    metadata = {}

    # Scan all fileset directories for this language
    for fileset_dir in lang_dir.iterdir():
        if not fileset_dir.is_dir():
            continue

        metadata_file = fileset_dir / "metadata.json"
        if not metadata_file.exists():
            continue

        try:
            with open(metadata_file) as f:
                data = json.load(f)
                fileset_id = data["fileset"]["id"]
                metadata[fileset_id] = data
        except Exception as e:
            continue

    return metadata


def verify_language_available(iso: str) -> bool:
    """Check if language exists in sorted/BB directory."""
    # Check if language directory exists
    lang_dir = SORTED_DIR / iso
    if lang_dir.exists() and lang_dir.is_dir():
        return True

    # Check for country-suffixed variants (iso_cc, iso_cc_2, etc.)
    if SORTED_DIR.exists():
        for entry in SORTED_DIR.iterdir():
            if entry.is_dir() and entry.name.startswith(f"{iso}_"):
                return True

    return False


def get_language_info(iso: str) -> Optional[Dict]:
    """Get language information from any metadata file."""
    metadata = load_language_metadata(iso)
    if not metadata:
        return None

    # Return language info from first available metadata
    first_metadata = next(iter(metadata.values()))
    lang_info = first_metadata["language"]

    # Ensure autonym field exists
    if "autonym" not in lang_info:
        lang_info["autonym"] = lang_info.get("name", "")

    return lang_info


def get_audio_filesets(iso: str, book_id: str) -> List[Dict]:
    """Get audio filesets for a specific book, prioritizing defaults.

    Priority order:
    1. Plain MP3, non-dramatized (N1DA or O1DA, no -opus suffix)
    2. Opus format, non-dramatized (N1DA-opus16 or O1DA-opus16)
    3. Plain MP3, dramatized (N2DA or O2DA, no -opus suffix)
    4. Opus format, dramatized (N2DA-opus16 or O2DA-opus16)

    Returns list sorted by priority, so caller should try in order.
    """
    metadata = load_language_metadata(iso)
    is_ot = book_id in OT_BOOKS

    audio_filesets = []
    for fileset_id, data in metadata.items():
        cat = data["categorization"]
        fileset_info = data["fileset"]

        if not cat["has_audio"]:
            continue

        # Skip excluded filesets (SA versions only - partial content handled by book_set logic)
        if fileset_id in _EXCLUSIONS["sa_versions"]:
            continue
        if fileset_id in _EXCLUSIONS["story_adaptations"]:
            continue

        # Check if this fileset covers the requested book
        book_set = cat["book_set"]
        if book_set == "FULL":
            audio_filesets.append(data)
        elif book_set == "OT" and is_ot:
            audio_filesets.append(data)
        elif book_set == "NT" and not is_ot:
            audio_filesets.append(data)
        # Skip PARTIAL - we don't know which books it contains without API query

    # Sort by priority: plain mp3 non-dramatized first
    def audio_priority(data):
        fileset_id = data["fileset"]["id"]
        # Non-dramatized (1) before dramatized (2)
        is_dramatized = "2DA" in fileset_id
        # Plain MP3 before opus
        is_opus = "-opus" in fileset_id
        return (is_dramatized, is_opus, fileset_id)

    audio_filesets.sort(key=audio_priority)

    return audio_filesets


def get_text_filesets(iso: str, book_id: str) -> List[Dict]:
    """Get text filesets for a specific book, prioritizing defaults.

    Priority order:
    1. Plain text (_ET)
    2. USX format (_ET-usx)
    3. JSON format (_ET-json)

    Returns list sorted by priority, so caller should try in order.
    """
    metadata = load_language_metadata(iso)
    is_ot = book_id in OT_BOOKS

    text_filesets = []
    for fileset_id, data in metadata.items():
        cat = data["categorization"]
        fileset_info = data["fileset"]

        if not cat["has_text"]:
            continue

        # Skip excluded filesets (SA versions only - partial content handled by book_set logic)
        if fileset_id in _EXCLUSIONS["sa_versions"]:
            continue
        if fileset_id in _EXCLUSIONS["story_adaptations"]:
            continue

        # Check if this fileset covers the requested book
        book_set = cat["book_set"]
        if book_set == "FULL":
            text_filesets.append(data)
        elif book_set == "OT" and is_ot:
            text_filesets.append(data)
        elif book_set == "NT" and not is_ot:
            text_filesets.append(data)
        # Skip PARTIAL - we don't know which books it contains without API query

    # Sort by priority: plain text first
    def text_priority(data):
        fileset_id = data["fileset"]["id"]
        if fileset_id.endswith("_ET") and not "-" in fileset_id:
            return (0, fileset_id)  # Plain text - highest priority
        elif fileset_id.endswith("-usx"):
            return (1, fileset_id)  # USX format
        elif fileset_id.endswith("-json"):
            return (2, fileset_id)  # JSON format
        else:
            return (3, fileset_id)  # Other formats

    text_filesets.sort(key=text_priority)

    return text_filesets


def get_syncable_pairs(iso: str, book_id: str) -> List[Tuple[str, str]]:
    """Get audio-text pairs that are marked as syncable."""
    metadata = load_language_metadata(iso)
    pairs = []

    for fileset_id, data in metadata.items():
        cat = data["categorization"]

        if not cat["syncable"]:
            continue

        # Extract pairs
        for pair in cat.get("audio_text_pairs", []):
            audio_id = pair["audio_fileset_id"]
            text_ids = pair["text_fileset_id"]

            if isinstance(text_ids, list):
                for text_id in text_ids:
                    pairs.append((audio_id, text_id))
            else:
                pairs.append((audio_id, text_ids))

    return pairs


def has_timing_available(iso: str, audio_fileset_id: str) -> bool:
    """Check if audio fileset has timing data available."""
    metadata = load_language_metadata(iso)
    if audio_fileset_id not in metadata:
        return False

    return metadata[audio_fileset_id]["download_ready"]["timing_available"]


def normalize_fileset_id(fileset_id: str) -> str:
    """Remove format suffixes for API calls.

    This is used for API calls that don't accept format suffixes.
    Different from distinct_id which is the Bible abbreviation.

    Examples:
        AAAMLTN1DA-opus16 -> AAAMLTN1DA
        ENGESV_ET-json -> ENGESV_ET
    """
    # Remove audio format suffixes
    audio_suffixes = ["-opus16", "-opus32", "-mp3-64", "-mp3-128", "-mp3"]
    for suffix in audio_suffixes:
        if fileset_id.endswith(suffix):
            return fileset_id[: -len(suffix)]

    # Remove text format suffixes
    text_suffixes = ["-json", "-usx"]
    for suffix in text_suffixes:
        if fileset_id.endswith(suffix):
            return fileset_id[: -len(suffix)]

    return fileset_id


def get_distinct_id_from_metadata(metadata: Dict) -> str:
    """Get distinct ID (Bible abbreviation) from metadata.

    The distinct ID is the Bible abbreviation, which is the common base
    for all filesets of the same Bible version.

    Examples:
        Bible abbr: AAAMLT
        - AAAMLTN1DA → AAAMLT (distinct ID)
        - AAAMLTN2DA-opus16 → AAAMLT (distinct ID)
        - AAAMLTN_ET → AAAMLT (distinct ID)

        Bible abbr: ENGESV
        - ENGESVN1DA → ENGESV (distinct ID)
        - ENGESVO1DA → ENGESV (distinct ID)
        - ENGESV_ET → ENGESV (distinct ID)
    """
    # Get Bible abbreviation from metadata
    bible_abbr = metadata.get("bible", {}).get("abbr", "")

    if bible_abbr:
        return bible_abbr

    # Fallback: derive from fileset ID (remove last 3-4 chars and suffixes)
    fileset_id = metadata.get("fileset", {}).get("id", "")

    # Remove format suffixes first
    base = fileset_id
    audio_suffixes = ["-opus16", "-opus32", "-mp3-64", "-mp3-128", "-mp3"]
    for suffix in audio_suffixes:
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break

    # Remove text format suffixes
    text_suffixes = ["_ET-json", "_ET-usx", "_ET"]
    for suffix in text_suffixes:
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break

    # Remove testament/type indicators (last 3-4 chars like N1DA, O2DA, etc.)
    # This is a fallback heuristic
    if len(base) > 6:
        # Check if last 4 chars match pattern like N1DA, O2DA
        if base[-4:-2] in ["N1", "O1", "N2", "O2"] and base[-2:] == "DA":
            base = base[:-4]
        # Check if last 3 chars match pattern like 1DA, 2DA
        elif base[-3:].endswith("DA"):
            base = base[:-3]

    return base


def get_language_directory_path(iso: str) -> str:
    """Get the language directory path.

    For now, simply returns the iso code. Country disambiguation can be
    added later if needed when conflicts are discovered.

    Args:
        iso: Three-letter language code

    Returns:
        Directory path relative to sorted/BB/ (just the iso for now)
    """
    return iso


def load_story_sets() -> Dict[str, str]:
    """Load story set configurations from story-set.conf.

    Returns:
        Dict mapping story set name to comma-separated book references
    """
    if not STORY_SET_CONFIG.exists():
        return {}

    story_sets = {}
    current_name = None
    current_books = []

    with open(STORY_SET_CONFIG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Check if this is a story set name (no commas, no colons)
            if "," not in line and ":" not in line:
                # Save previous story set if any
                if current_name:
                    story_sets[current_name] = ",".join(current_books)

                # Start new story set
                current_name = line
                current_books = []
            else:
                # This is a book reference line
                if current_name:
                    current_books.append(line)

        # Save last story set
        if current_name:
            story_sets[current_name] = ",".join(current_books)

    return story_sets


def load_regions() -> Dict[str, List[str]]:
    """
    Load region definitions from config/regions.conf.

    Returns:
        Dictionary mapping region names to lists of ISO codes
    """
    if not REGIONS_CONFIG.exists():
        log(f"Warning: Regions config not found: {REGIONS_CONFIG}", "WARNING")
        return {}

    regions = {}
    current_region = None
    current_languages = []

    with open(REGIONS_CONFIG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Check if this is a region name (no commas, not starting with lowercase)
            if "," not in line and not line[0].islower():
                # Save previous region if exists
                if current_region and current_languages:
                    regions[current_region] = current_languages

                # Start new region
                current_region = line
                current_languages = []
            else:
                # This is a language list
                if current_region:
                    # Split by comma and clean
                    langs = [lang.strip() for lang in line.split(",")]
                    current_languages.extend(langs)

        # Save last region
        if current_region and current_languages:
            regions[current_region] = current_languages

    return regions


def get_languages_by_region(region: str) -> List[str]:
    """
    Get list of language ISO codes for a specific region.

    Args:
        region: Region name (e.g., "Finland", "India", "European Union", "ALL")

    Returns:
        List of language ISO codes
    """
    # Handle ALL as special case - return all available languages
    if region == "ALL":
        languages = []

        # Check if sorted/BB has any languages
        if SORTED_DIR.exists():
            for lang_dir in SORTED_DIR.iterdir():
                if lang_dir.is_dir():
                    # Extract base ISO code (handle both "eng" and "eng_US" formats)
                    iso = lang_dir.name.split("_")[0]
                    if iso not in languages and len(iso) == 3:
                        languages.append(iso)

        # If no languages found, error
        if not languages:
            log(
                "No languages found in sorted/BB directory.",
                "ERROR",
            )
            log("Please run: python sort_cache_data.py", "INFO")
            sys.exit(1)

        return sorted(languages)

    regions = load_regions()

    if region not in regions:
        available = ", ".join(sorted(regions.keys())[:10])
        log(f"Error: Region '{region}' not found in {REGIONS_CONFIG}", "ERROR")
        log(f"Available regions: {available}... (and {len(regions) - 10} more)", "INFO")
        sys.exit(1)

    return regions[region]


def get_languages_by_book_set(book_set: str) -> List[str]:
    """
    Get list of language ISO codes filtered by book-set category.

    Categories:
    - ALL: All available languages
    - SYNC_FULL: Languages with syncable full Bible (OT+NT)
    - SYNC_NT: Languages with syncable New Testament
    - SYNC_OT: Languages with syncable Old Testament
    - TIMING_FULL: Languages with timing data for full Bible
    - TIMING_NT: Languages with timing data for New Testament
    - TIMING_OT: Languages with timing data for Old Testament

    Args:
        book_set: Category name

    Returns:
        List of language ISO codes
    """
    languages = []
    languages_to_check = []

    # Get list of languages to check from sorted/BB
    if SORTED_DIR.exists():
        for lang_dir in SORTED_DIR.iterdir():
            if lang_dir.is_dir():
                # Extract base ISO code (handle both "eng" and "eng_US" formats)
                iso = lang_dir.name.split("_")[0]
                if len(iso) == 3 and iso not in languages_to_check:
                    languages_to_check.append(iso)

    # If no languages found, error
    if not languages_to_check:
        log("No languages found in sorted/BB directory.", "ERROR")
        log("Please run: python sort_cache_data.py", "INFO")
        sys.exit(1)

    # Check each language against the book-set criteria
    for iso in languages_to_check:
        metadata_dict = load_language_metadata(iso)

        if not metadata_dict:
            continue

        # Check if language matches the book-set criteria
        if book_set == "ALL":
            languages.append(iso)
        elif book_set == "SYNC_FULL":
            # Has syncable audio for both OT and NT
            has_ot = False
            has_nt = False
            for fileset_id, metadata in metadata_dict.items():
                cat = metadata["categorization"]
                if cat.get("syncable") and cat.get("data_source") == "sync":
                    book_set_type = cat.get("book_set")
                    if book_set_type == "FULL":
                        has_ot = has_nt = True
                        break
                    elif book_set_type == "OT":
                        has_ot = True
                    elif book_set_type == "NT":
                        has_nt = True
            if has_ot and has_nt:
                languages.append(iso)
        elif book_set == "SYNC_NT":
            # Has syncable audio for NT
            for fileset_id, metadata in metadata_dict.items():
                cat = metadata["categorization"]
                if cat.get("syncable") and cat.get("data_source") == "sync":
                    book_set_type = cat.get("book_set")
                    if book_set_type in ["NT", "FULL"]:
                        languages.append(iso)
                        break
        elif book_set == "SYNC_OT":
            # Has syncable audio for OT
            for fileset_id, metadata in metadata_dict.items():
                cat = metadata["categorization"]
                if cat.get("syncable") and cat.get("data_source") == "sync":
                    book_set_type = cat.get("book_set")
                    if book_set_type in ["OT", "FULL"]:
                        languages.append(iso)
                        break
        elif book_set == "TIMING_FULL":
            # Has timing data for both OT and NT
            has_ot = False
            has_nt = False
            for fileset_id, metadata in metadata_dict.items():
                cat = metadata["categorization"]
                if cat.get("has_timing") and cat.get("data_source") == "timing":
                    book_set_type = cat.get("book_set")
                    if book_set_type == "FULL":
                        has_ot = has_nt = True
                        break
                    elif book_set_type == "OT":
                        has_ot = True
                    elif book_set_type == "NT":
                        has_nt = True
            if has_ot and has_nt:
                languages.append(iso)
        elif book_set == "TIMING_NT":
            # Has timing data for NT
            for fileset_id, metadata in metadata_dict.items():
                cat = metadata["categorization"]
                if cat.get("has_timing") and cat.get("data_source") == "timing":
                    book_set_type = cat.get("book_set")
                    if book_set_type in ["NT", "FULL"]:
                        languages.append(iso)
                        break
        elif book_set == "TIMING_OT":
            # Has timing data for OT
            for fileset_id, metadata in metadata_dict.items():
                cat = metadata["categorization"]
                if cat.get("has_timing") and cat.get("data_source") == "timing":
                    book_set_type = cat.get("book_set")
                    if book_set_type in ["OT", "FULL"]:
                        languages.append(iso)
                        break

    return sorted(languages)


def make_api_request(endpoint: str, params: Dict = None) -> Optional[Dict]:
    """Make a direct API request."""
    if not BIBLE_API_KEY:
        log("BIBLE_API_KEY not found in environment", "ERROR")
        return None

    url = f"{BIBLE_API_BASE_URL}{endpoint}"

    # Add API version and key
    if params is None:
        params = {}
    params["v"] = "4"
    params["key"] = BIBLE_API_KEY

    try:
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log(f"API request failed: {e}", "ERROR")
        return None


def get_audio_path(audio_fileset_id: str, book_id: str, chapter: int) -> Optional[str]:
    """Get audio file path from API."""
    endpoint = f"/bibles/filesets/{audio_fileset_id}/{book_id}/{chapter}"

    data = make_api_request(endpoint)
    if not data or "data" not in data:
        return None

    items = data["data"]
    if not items or len(items) == 0:
        return None

    # Get the path from first item
    return items[0].get("path")


def get_text_content(text_fileset_id: str, book_id: str, chapter: int) -> Optional[str]:
    """Get text content from API."""
    endpoint = f"/bibles/filesets/{text_fileset_id}/{book_id}/{chapter}"

    data = make_api_request(endpoint)
    if not data or "data" not in data:
        return None

    items = data["data"]
    if not items:
        return None

    # Concatenate all verse texts
    text_parts = []
    for item in items:
        verse_text = item.get("verse_text", "")
        if verse_text:
            text_parts.append(verse_text)

    return "\n".join(text_parts) if text_parts else None


def download_audio_file(url: str, output_path: Path) -> bool:
    """Download audio file from URL."""
    try:
        response = requests.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)
        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return True
    except requests.exceptions.RequestException as e:
        log(f"Download failed: {e}", "ERROR")
        return False


def save_text_file(text: str, output_path: Path) -> bool:
    """Save text content to file."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        return True
    except Exception as e:
        log(f"Failed to save text: {e}", "ERROR")
        return False


def get_timing_data(
    audio_fileset_id: str, book_id: str, chapter: int
) -> Optional[Dict]:
    """Get timing data from API for a specific chapter."""
    # Normalize fileset ID - timing API doesn't work with suffixes like -opus16
    base_fileset_id = normalize_fileset_id(audio_fileset_id)
    endpoint = f"/timestamps/{base_fileset_id}/{book_id}/{chapter}"

    data = make_api_request(endpoint)
    if not data:
        return None

    if "error" in data:
        return None

    if "data" in data:
        timing_data = data["data"]
        # Check if data array is not empty
        if timing_data and len(timing_data) > 0:
            return timing_data
        return None

    return None


def filter_duplicate_formats(filesets: List[str]) -> List[str]:
    """
    Filter out duplicate format variations, keeping only one representative per base.

    For text filesets, filters out format suffixes like -json, -usx, keeping only _ET.
    For audio filesets, filters out codec variations like -opus16, keeping base format.

    Examples:
        ENGWEBN_ET, ENGWEBN_ET-json, ENGWEBN_ET-usx -> ENGWEBN_ET
        ENGESVO2DA, ENGESVO2DA-opus16 -> ENGESVO2DA

    Args:
        filesets: List of fileset IDs

    Returns:
        Filtered list with one representative per base fileset
    """
    # Group by base fileset (remove format suffixes)
    base_groups = defaultdict(list)

    for fileset_id in filesets:
        # Remove common suffixes to find base
        base = fileset_id
        for suffix in ["-json", "-usx", "-xml", "-opus16", "-opus32", "-mp3"]:
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        base_groups[base].append(fileset_id)

    # Select one representative per base
    filtered = []
    for base, variants in base_groups.items():
        # Prefer plain _ET for text, or base format for audio
        if any("_ET" == fs[-3:] for fs in variants):
            # Prefer plain _ET text format
            filtered.append([fs for fs in variants if fs.endswith("_ET")][0])
        elif any(fs == base for fs in variants):
            # Prefer base version without suffix
            filtered.append(base)
        else:
            # Take first variant
            filtered.append(variants[0])

    return filtered


def filter_dramatized_versions(filesets: List[str]) -> List[str]:
    """
    Filter out dramatized versions when non-dramatized version exists.

    Dramatized check: Position -3 (third from end) == '2'
    Non-dramatized: Position -3 == '1'

    Example:
        If both ENGWEBN1DA and ENGWEBN2DA exist, keep only ENGWEBN1DA

    Args:
        filesets: List of fileset IDs

    Returns:
        Filtered list with dramatized versions removed where non-dramatized exists
    """
    # Group by base pattern (all except position -3)
    base_groups = defaultdict(list)

    for fs_id in filesets:
        if len(fs_id) >= 3:
            # Create base key: everything except position -3
            base = fs_id[:-3] + fs_id[-2:]
            base_groups[base].append(fs_id)

    filtered = []
    for base, fs_list in base_groups.items():
        # Check for version 1 and version 2
        has_version_1 = any(len(fs) >= 3 and fs[-3] == "1" for fs in fs_list)
        version_2_ids = [fs for fs in fs_list if len(fs) >= 3 and fs[-3] == "2"]

        if has_version_1 and version_2_ids:
            # Keep only non-dramatized (version 1)
            filtered.extend([fs for fs in fs_list if fs not in version_2_ids])
        else:
            # Keep all
            filtered.extend(fs_list)

    return filtered


def save_timing_file(timing_data: Dict, output_path: Path) -> bool:
    """Save timing data to JSON file."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(timing_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        log(f"Failed to save timing data: {e}", "ERROR")
        return False


def copy_version_metadata(iso: str, fileset_id: str) -> bool:
    """
    No longer needed - metadata is not stored in new sorted/BB structure.
    Files are self-documenting via filenames containing full fileset IDs.
    """
    return True


def download_book_chapter(
    iso: str,
    book_id: str,
    chapter: int,
    audio_filesets: List[Dict],
    text_filesets: List[Dict],
    force: bool = False,
) -> Tuple[bool, bool, bool]:
    """
    Download a single chapter for ALL available versions (audio, text, and timing).

    Downloads all available Bible versions into downloads/BB structure:
    downloads/BB/{iso}/{distinct_id}/{BOOK}/{BOOK}_{CHAPTER:03d}_{FULL_FILESET_ID}.{ext}

    The distinct_id is the Bible abbreviation (e.g., AAAMLT, ENGESV).
    Each book gets its own subdirectory.

    Returns:
        Tuple of (any_audio_success, any_text_success, any_timing_success)
    """
    chapter_str = f"{chapter:03d}"
    any_audio_success = False
    any_text_success = False
    any_timing_success = False

    # Try audio filesets - download one per distinct_id (Bible version)
    downloaded_distinct_ids = set()

    for audio_metadata in audio_filesets:
        audio_fileset_id = audio_metadata["fileset"]["id"]
        distinct_id = get_distinct_id_from_metadata(audio_metadata)

        # Skip if we already downloaded audio for this distinct_id
        if distinct_id in downloaded_distinct_ids:
            continue

        # Create directory structure: downloads/BB/{iso}/{distinct_id}/{book}/
        lang_path = get_language_directory_path(iso)
        book_dir = OUTPUT_DIR / lang_path / distinct_id / book_id
        book_dir.mkdir(parents=True, exist_ok=True)

        # Check if ANY audio file already exists in this directory (skip download)
        existing_audio = list(book_dir.glob(f"{book_id}_{chapter_str}_*.mp3"))
        if existing_audio and not force:
            audio_path = existing_audio[0]
            log(
                f"Audio already exists: {lang_path}/{distinct_id}/{book_id}/{audio_path.name}",
                "INFO",
            )
            any_audio_success = True

            # Check for timing file for existing audio
            existing_fileset_id = audio_path.stem.split("_", 2)[-1]
            timing_filename = (
                f"{book_id}_{chapter_str}_{existing_fileset_id}_timing.json"
            )
            timing_path = book_dir / timing_filename
            if timing_path.exists():
                any_timing_success = True
            elif has_timing_available(iso, existing_fileset_id):
                log(
                    f"Downloading timing for: {lang_path}/{distinct_id}/{book_id}/{timing_filename}",
                    "INFO",
                )
                timing_data = get_timing_data(existing_fileset_id, book_id, chapter)
                if timing_data:
                    if save_timing_file(timing_data, timing_path):
                        log(
                            f"✓ Timing saved: {lang_path}/{distinct_id}/{book_id}/{timing_filename}",
                            "SUCCESS",
                        )
                        any_timing_success = True
            # Mark this distinct_id as downloaded
            downloaded_distinct_ids.add(distinct_id)
            continue  # Continue to next distinct_id

        # Filename includes FULL fileset ID
        audio_filename = f"{book_id}_{chapter_str}_{audio_fileset_id}.mp3"
        audio_path = book_dir / audio_filename

        # Get audio file URL
        log(
            f"Downloading audio: {lang_path}/{distinct_id}/{book_id}/{audio_filename}",
            "INFO",
        )
        audio_url = get_audio_path(audio_fileset_id, book_id, chapter)

        if not audio_url:
            log(
                f"Audio not available for {book_id} {chapter} in {audio_fileset_id}",
                "WARNING",
            )
            log_download_error(
                iso,
                book_id,
                chapter,
                content_type="audio",
                error_type="no_audio_available",
                fileset=audio_fileset_id,
                distinct_id=distinct_id,
                format_type=audio_metadata["fileset"].get("type", "unknown"),
                details=f"No audio path returned for fileset {audio_fileset_id}",
            )
            continue  # Try next audio format

        # Download audio
        if download_audio_file(audio_url, audio_path):
            log(
                f"✓ Audio saved: {lang_path}/{distinct_id}/{book_id}/{audio_filename}",
                "SUCCESS",
            )
            any_audio_success = True

            # Try to download timing data if available
            if has_timing_available(iso, audio_fileset_id):
                timing_filename = (
                    f"{book_id}_{chapter_str}_{audio_fileset_id}_timing.json"
                )
                timing_path = book_dir / timing_filename

                if not timing_path.exists() or force:
                    log(
                        f"Downloading timing: {lang_path}/{distinct_id}/{book_id}/{timing_filename}",
                        "INFO",
                    )
                    timing_data = get_timing_data(audio_fileset_id, book_id, chapter)

                    if timing_data:
                        if save_timing_file(timing_data, timing_path):
                            log(
                                f"✓ Timing saved: {lang_path}/{distinct_id}/{book_id}/{timing_filename}",
                                "SUCCESS",
                            )
                            any_timing_success = True
                        else:
                            log(
                                f"Failed to save timing data for {book_id} {chapter} in {audio_fileset_id}",
                                "WARNING",
                            )
                            log_download_error(
                                iso,
                                book_id,
                                chapter,
                                content_type="timing",
                                error_type="timing_save_failed",
                                fileset=audio_fileset_id,
                                distinct_id=distinct_id,
                                details=f"Failed to save timing file for fileset {audio_fileset_id}",
                            )
                    else:
                        log(
                            f"Timing data not available for {book_id} {chapter} in {audio_fileset_id}",
                            "WARNING",
                        )
                        log_download_error(
                            iso,
                            book_id,
                            chapter,
                            content_type="timing",
                            error_type="no_timing_available",
                            fileset=audio_fileset_id,
                            distinct_id=distinct_id,
                            details=f"No timing data returned for fileset {audio_fileset_id}",
                        )
                else:
                    any_timing_success = True

            # Mark this distinct_id as downloaded, continue to try other Bible versions
            downloaded_distinct_ids.add(distinct_id)
            continue  # Continue to next distinct_id

        # If we reach here, download failed - try next fileset for same or different distinct_id
        log(
            f"Failed to download audio from {audio_fileset_id}, trying next format...",
            "WARNING",
        )
        log_download_error(
            iso,
            book_id,
            chapter,
            content_type="audio",
            error_type="audio_download_failed",
            fileset=audio_fileset_id,
            distinct_id=distinct_id,
            format_type=audio_metadata["fileset"].get("type", "unknown"),
            details=f"Failed to download audio file from {audio_fileset_id}",
        )
        # Continue to next audio format

    # Try text filesets - download one per distinct_id (Bible version)
    downloaded_text_distinct_ids = set()

    for text_metadata in text_filesets:
        text_fileset_id = text_metadata["fileset"]["id"]
        distinct_id = get_distinct_id_from_metadata(text_metadata)

        # Skip if we already downloaded text for this distinct_id
        if distinct_id in downloaded_text_distinct_ids:
            continue

        # Create directory structure: downloads/BB/{iso}/{distinct_id}/{book}/
        lang_path = get_language_directory_path(iso)
        book_dir = OUTPUT_DIR / lang_path / distinct_id / book_id
        book_dir.mkdir(parents=True, exist_ok=True)

        # Check if ANY text file already exists in this directory (skip download)
        existing_text = list(book_dir.glob(f"{book_id}_{chapter_str}_*.txt"))
        if existing_text and not force:
            log(
                f"Text already exists: {lang_path}/{distinct_id}/{book_id}/{existing_text[0].name}",
                "INFO",
            )
            any_text_success = True
            # Mark this distinct_id as downloaded
            downloaded_text_distinct_ids.add(distinct_id)
            continue  # Continue to next distinct_id

        # Filename includes FULL fileset ID
        text_filename = f"{book_id}_{chapter_str}_{text_fileset_id}.txt"
        text_path = book_dir / text_filename

        # Get text content
        log(
            f"Downloading text: {lang_path}/{distinct_id}/{book_id}/{text_filename}",
            "INFO",
        )
        text_content = get_text_content(text_fileset_id, book_id, chapter)

        if not text_content:
            log(
                f"Text not available for {book_id} {chapter} in {text_fileset_id}",
                "WARNING",
            )
            log_download_error(
                iso,
                book_id,
                chapter,
                content_type="text",
                error_type="no_text_available",
                fileset=text_fileset_id,
                distinct_id=distinct_id,
                details=f"No text content returned for fileset {text_fileset_id}",
            )
            continue  # Try next text format

        # Save text
        if save_text_file(text_content, text_path):
            log(
                f"✓ Text saved: {lang_path}/{distinct_id}/{book_id}/{text_filename}",
                "SUCCESS",
            )
            any_text_success = True
            # Mark this distinct_id as downloaded, continue to try other Bible versions
            downloaded_text_distinct_ids.add(distinct_id)
            continue  # Continue to next distinct_id

        # If we reach here, download failed - try next fileset
        log(
            f"Failed to save text from {text_fileset_id}, trying next format...",
            "WARNING",
        )
        log_download_error(
            iso,
            book_id,
            chapter,
            content_type="text",
            error_type="text_save_failed",
            fileset=text_fileset_id,
            distinct_id=distinct_id,
            details=f"Failed to save text file from {text_fileset_id}",
        )
        # Continue to next text format

    return any_audio_success, any_text_success, any_timing_success


def download_book(
    iso: str,
    book_id: str,
    chapters: Optional[List[int]] = None,
    force: bool = False,
) -> Tuple[int, int, int]:
    """
    Download all chapters of a book.

    Returns:
        Tuple of (audio_count, text_count, timing_count)
    """
    max_chapters = ALL_BOOKS.get(book_id, 0)
    if chapters is None:
        chapters = list(range(1, max_chapters + 1))

    # Validate chapters
    for chapter in chapters:
        if chapter < 1 or chapter > max_chapters:
            log(
                f"Invalid chapter {chapter} for {book_id} (max: {max_chapters})",
                "ERROR",
            )
            return 0, 0, 0

    # Get available filesets
    audio_filesets = get_audio_filesets(iso, book_id)
    text_filesets = get_text_filesets(iso, book_id)

    if not audio_filesets and not text_filesets:
        log(f"No filesets available for {book_id}", "ERROR")
        return 0, 0, 0

    log(
        f"Downloading {book_id} chapters {min(chapters)}-{max(chapters)} ({len(chapters)} chapters)",
        "INFO",
    )
    log(f"Audio filesets available: {len(audio_filesets)}", "INFO")
    log(f"Text filesets available: {len(text_filesets)}", "INFO")

    audio_count = 0
    text_count = 0
    timing_count = 0

    for chapter in chapters:
        audio_ok, text_ok, timing_ok = download_book_chapter(
            iso, book_id, chapter, audio_filesets, text_filesets, force
        )

        if audio_ok:
            audio_count += 1
        if text_ok:
            text_count += 1
        if timing_ok:
            timing_count += 1

    return audio_count, text_count, timing_count


def expand_story_sets(books_arg: str) -> str:
    """Expand story set names in books argument to actual book references.

    Args:
        books_arg: Original --books argument (may contain story set names)

    Returns:
        Expanded books argument with story sets replaced by their book references
    """
    # Load story sets
    story_sets = load_story_sets()
    if not story_sets:
        return books_arg

    # Split the books argument
    parts = [part.strip() for part in books_arg.split(",")]
    expanded_parts = []

    for part in parts:
        # Check if this part is a story set name
        if part in story_sets:
            # Expand the story set
            expanded_parts.append(story_sets[part])
        else:
            # Keep as-is
            expanded_parts.append(part)

    return ",".join(expanded_parts)


def parse_chapter_spec(spec: str) -> Optional[List[int]]:
    """Parse chapter specification like 'GEN:1-5' or 'MAT:1,3,5-7'."""
    if ":" not in spec:
        return None

    parts = spec.split(":", 1)
    if len(parts) != 2:
        return None

    chapter_spec = parts[1]
    chapters = []

    for part in chapter_spec.split(","):
        part = part.strip()
        if "-" in part:
            # Range: 1-5
            range_parts = part.split("-")
            if len(range_parts) != 2:
                return None
            try:
                start = int(range_parts[0])
                end = int(range_parts[1])
                chapters.extend(range(start, end + 1))
            except ValueError:
                return None
        else:
            # Single chapter: 1
            try:
                chapters.append(int(part))
            except ValueError:
                return None

    return sorted(list(set(chapters)))


def main():
    parser = argparse.ArgumentParser(
        description="Download Bible content using sorted metadata",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Book-set categories for batch downloading:
  ALL           All available languages (default)
  SYNC_FULL     Languages with syncable full Bible (OT+NT)
  SYNC_NT       Languages with syncable New Testament
  SYNC_OT       Languages with syncable Old Testament
  TIMING_FULL   Languages with timing data for full Bible
  TIMING_NT     Languages with timing data for New Testament
  TIMING_OT     Languages with timing data for Old Testament

Region filtering (can be combined with book-set):
  --region Finland      Only Finnish languages (fin, swe, smi)
  --region India        Only Indian languages (hin, ben, tel, ...)
  --region "European Union"  All EU languages

Examples:
  # Single language
  python download_language_content.py eng --books GEN,MAT
  python download_language_content.py spa --books GEN:1-5

  # Batch by category
  python download_language_content.py --book-set SYNC_NT --books MAT:1
  python download_language_content.py --book-set TIMING_FULL --books PSA:117
  python download_language_content.py --book-set ALL --books GEN:1-3

  # With region filter
  python download_language_content.py --book-set TIMING_NT --region Finland --books MAT:1
  python download_language_content.py --book-set ALL --region India --books GEN:1
        """,
    )
    parser.add_argument(
        "language",
        nargs="?",
        help="Language ISO code (required unless --book-set is used)",
    )
    parser.add_argument(
        "--book-set",
        choices=[
            "ALL",
            "SYNC_FULL",
            "SYNC_NT",
            "SYNC_OT",
            "TIMING_FULL",
            "TIMING_NT",
            "TIMING_OT",
        ],
        help="Download multiple languages by category (default: ALL if no language specified)",
    )
    parser.add_argument(
        "--region",
        default="ALL",
        help="Filter languages by region/country (default: ALL, e.g., Finland, India, 'European Union')",
    )
    parser.add_argument(
        "--books",
        help="Comma-separated list of book codes (e.g., GEN,EXO,MAT) or with chapters (GEN:1-5)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if files exist",
    )

    args = parser.parse_args()

    # Load exclusions
    load_exclusions()

    # Validate arguments
    if args.book_set and args.language:
        log("Error: Cannot specify both language and --book-set", "ERROR")
        sys.exit(1)

    if args.region != "ALL" and args.language:
        log("Error: Cannot specify both language and --region", "ERROR")
        sys.exit(1)

    # If only --books is specified, default to --region ALL
    if not args.book_set and not args.language:
        if args.region == "ALL" and args.books:
            # This is valid - download for all languages with specified books
            pass
        elif args.region == "ALL" and not args.books:
            log("Error: Must specify --books when using default region (ALL)", "ERROR")
            parser.print_help()
            sys.exit(1)

    if (
        not args.book_set
        and not args.language
        and args.region == "ALL"
        and not args.books
    ):
        log("Error: Must specify either language, --book-set, or --books", "ERROR")
        parser.print_help()
        sys.exit(1)

    # Verify API key
    if not BIBLE_API_KEY:
        log("Error: BIBLE_API_KEY not found in environment", "ERROR")
        log("Please create a .env file with: BIBLE_API_KEY=your_key_here", "ERROR")
        sys.exit(1)

    # Verify sorted/BB directory exists (metadata source)
    if not SORTED_DIR.exists():
        log(f"Error: Sorted directory not found: {SORTED_DIR}", "ERROR")
        log("Please run: python sort_cache_data.py", "ERROR")
        sys.exit(1)

    # Handle batch download by book-set (optionally with region filter)
    if args.book_set:
        log(f"Batch download mode: {args.book_set}", "INFO")
        languages = get_languages_by_book_set(args.book_set)

        # Apply region filter if specified
        if args.region:
            region_languages = get_languages_by_region(args.region)
            # Intersection: only languages that match both book-set AND region
            languages = [lang for lang in languages if lang in region_languages]
            log(f"Region filter applied: {args.region}", "INFO")

        if not languages:
            if args.region:
                log(
                    f"No languages found for book-set '{args.book_set}' in region '{args.region}'",
                    "ERROR",
                )
            else:
                log(f"No languages found for book-set: {args.book_set}", "ERROR")
            sys.exit(1)

        if args.region:
            log(
                f"Found {len(languages)} languages in category {args.book_set} for region {args.region}",
                "INFO",
            )
        else:
            log(f"Found {len(languages)} languages in category {args.book_set}", "INFO")

        if not args.books:
            log("Error: --books parameter required for batch download", "ERROR")
            sys.exit(1)

        # Expand story sets in books argument
        expanded_books = expand_story_sets(args.books)
        if expanded_books != args.books:
            log(f"Story set expanded: {args.books} -> {expanded_books}", "INFO")

        # Download each language
        total_languages = len(languages)
        for idx, iso in enumerate(languages, 1):
            log("", "INFO")
            log("=" * 70, "INFO")
            log(f"Processing language {idx}/{total_languages}: {iso}", "INFO")
            log("=" * 70, "INFO")

            # Get language info
            lang_info = get_language_info(iso)
            if not lang_info:
                log(f"Could not load language info for '{iso}' - skipping", "WARNING")
                continue

            log(f"Language: {lang_info['name']} ({iso})", "INFO")
            log(f"Autonym: {lang_info['autonym']}", "INFO")

            # Determine which books to download
            books_to_download = []
            book_chapters = {}

            # Parse book list
            for book_spec in expanded_books.split(","):
                book_spec = book_spec.strip().upper()

                # Check if it has chapter specification
                chapters = parse_chapter_spec(book_spec)
                if chapters:
                    book_id = book_spec.split(":")[0]
                    if book_id not in ALL_BOOKS:
                        log(f"Unknown book code: {book_id}", "WARNING")
                        continue
                    books_to_download.append(book_id)
                    book_chapters[book_id] = chapters
                else:
                    if book_spec not in ALL_BOOKS:
                        log(f"Unknown book code: {book_spec}", "WARNING")
                        continue
                    books_to_download.append(book_spec)

            if not books_to_download:
                log("No valid books to download", "WARNING")
                continue

            log(f"Books to download: {len(books_to_download)}", "INFO")

            # Download books
            for book_id in books_to_download:
                chapters = book_chapters.get(book_id)
                download_book(iso, book_id, chapters, args.force)

        log("", "INFO")
        log("=" * 70, "INFO")
        log(f"Batch download complete: {total_languages} languages processed", "INFO")
        log("=" * 70, "INFO")
        return

    # Check if region filter is used without book-set (use as standalone filter)
    if args.region and not args.book_set and not args.language:
        log(f"Region filter mode: {args.region}", "INFO")
        languages = get_languages_by_region(args.region)

        if not languages:
            log(f"No languages found for region: {args.region}", "ERROR")
            sys.exit(1)

        log(f"Found {len(languages)} languages in region {args.region}", "INFO")

        if not args.books:
            log("Error: --books parameter required for region download", "ERROR")
            sys.exit(1)

        # Expand story sets in books argument
        expanded_books = expand_story_sets(args.books)
        if expanded_books != args.books:
            log(f"Story set expanded: {args.books} -> {expanded_books}", "INFO")

        # Download each language in region
        total_languages = len(languages)
        for idx, iso in enumerate(languages, 1):
            log("", "INFO")
            log("=" * 70, "INFO")
            log(f"Processing language {idx}/{total_languages}: {iso}", "INFO")
            log("=" * 70, "INFO")

            # Get language info
            lang_info = get_language_info(iso)
            if not lang_info:
                log(f"Could not load language info for '{iso}' - skipping", "WARNING")
                continue

            log(f"Language: {lang_info['name']} ({iso})", "INFO")
            log(f"Autonym: {lang_info['autonym']}", "INFO")

            # Determine which books to download
            books_to_download = []
            book_chapters = {}

            # Parse book list
            for book_spec in expanded_books.split(","):
                book_spec = book_spec.strip().upper()

                # Check if it has chapter specification
                chapters = parse_chapter_spec(book_spec)
                if chapters:
                    book_id = book_spec.split(":")[0]
                    if book_id not in ALL_BOOKS:
                        log(f"Unknown book code: {book_id}", "WARNING")
                        continue
                    books_to_download.append(book_id)
                    book_chapters[book_id] = chapters
                else:
                    if book_spec not in ALL_BOOKS:
                        log(f"Unknown book code: {book_spec}", "WARNING")
                        continue
                    books_to_download.append(book_spec)

            if not books_to_download:
                log("No valid books to download", "WARNING")
                continue

            log(f"Books to download: {len(books_to_download)}", "INFO")

            # Download books
            for book_id in books_to_download:
                chapters = book_chapters.get(book_id)
                download_book(iso, book_id, chapters, args.force)

        log("", "INFO")
        log("=" * 70, "INFO")
        log(f"Region download complete: {total_languages} languages processed", "INFO")
        log("=" * 70, "INFO")
        return

    # Single language download mode
    iso = args.language.lower()

    # Verify language exists
    if not verify_language_available(iso):
        log(f"Error: Language '{iso}' not found in sorted directory", "ERROR")
        log(f"Please check: {SORTED_DIR / iso}", "ERROR")
        sys.exit(1)

    # Get language info
    lang_info = get_language_info(iso)
    if not lang_info:
        log(f"Error: Could not load language info for '{iso}'", "ERROR")
        sys.exit(1)

    log(f"Language: {lang_info['name']} ({iso})", "INFO")
    log(f"Autonym: {lang_info['autonym']}", "INFO")

    # Determine which books to download
    books_to_download = []
    book_chapters = {}

    if args.books:
        # Expand story sets in books argument
        expanded_books = expand_story_sets(args.books)
        if expanded_books != args.books:
            log(f"Story set expanded: {args.books} -> {expanded_books}", "INFO")

        # Parse book list
        for book_spec in expanded_books.split(","):
            book_spec = book_spec.strip().upper()

            # Check if it has chapter specification
            chapters = parse_chapter_spec(book_spec)
            if chapters:
                book_id = book_spec.split(":")[0]
                if book_id not in ALL_BOOKS:
                    log(f"Unknown book code: {book_id}", "ERROR")
                    sys.exit(1)
                books_to_download.append(book_id)
                book_chapters[book_id] = chapters
            else:
                if book_spec not in ALL_BOOKS:
                    log(f"Unknown book code: {book_spec}", "ERROR")
                    sys.exit(1)
                books_to_download.append(book_spec)
    else:
        # Download all available books
        metadata = load_language_metadata(iso)
        book_sets = set()
        for fileset_id, data in metadata.items():
            book_set = data["categorization"].get("book_set")
            if book_set:
                book_sets.add(book_set)

        if "FULL" in book_sets:
            books_to_download = list(ALL_BOOKS.keys())
        elif "OT" in book_sets and "NT" in book_sets:
            books_to_download = list(ALL_BOOKS.keys())
        elif "NT" in book_sets:
            books_to_download = list(NT_BOOKS.keys())
        elif "OT" in book_sets:
            books_to_download = list(OT_BOOKS.keys())
        else:
            # Try downloading all and let it fail gracefully
            books_to_download = list(ALL_BOOKS.keys())

    if not books_to_download:
        log("No books to download", "ERROR")
        sys.exit(1)

    log(f"Books to download: {len(books_to_download)}", "INFO")

    # Download books
    total_audio = 0
    total_text = 0
    total_timing = 0

    for book_id in books_to_download:
        chapters = book_chapters.get(book_id)
        audio_count, text_count, timing_count = download_book(
            iso, book_id, chapters, args.force
        )

        total_audio += audio_count
        total_text += text_count
        total_timing += timing_count

    # Summary
    log("\n" + "=" * 50, "INFO")
    log("Download Summary", "INFO")
    log("=" * 50, "INFO")
    log(f"Language: {lang_info['name']} ({iso})", "INFO")
    log(f"Books processed: {len(books_to_download)}", "INFO")
    log(f"Audio chapters: {total_audio}", "INFO")
    log(f"Text chapters: {total_text}", "INFO")
    log(f"Timing files: {total_timing}", "INFO")
    log(f"Output directory: downloads/BB/{iso}", "INFO")

    if iso in _ERROR_LOG and _ERROR_LOG[iso]["errors"]:
        error_summary = get_error_summary(iso)
        log(f"\n⚠ Errors Summary:", "WARNING")
        log(
            f"  Chapters with errors: {error_summary['total_chapters_with_errors']}",
            "WARNING",
        )
        log(f"  Audio errors: {error_summary['audio_errors']}", "WARNING")
        log(f"  Text errors: {error_summary['text_errors']}", "WARNING")
        log(f"  Timing errors: {error_summary['timing_errors']}", "WARNING")
        log(f"  Details: {DOWNLOAD_LOG_DIR / f'{iso}_errors.json'}", "INFO")


if __name__ == "__main__":
    main()
