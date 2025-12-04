#!/usr/bin/env python3
"""
Sort and organize API cache data into a downloads-like directory structure.

This script is FULLY INDEPENDENT - no dependencies on stats/ directory.
It computes all categorization logic directly from api-cache/.

Key features:
- Single script execution: api-cache/ → sorted/BB/
- Computes syncable pairs on-the-fly
- Filters dramatized versions automatically
- Determines book sets from fileset structure
- Matches audio to text by prefix
- Identifies timing availability
- Creates comprehensive metadata for each fileset

Usage:
    python sort_cache_data.py

Output:
    sorted/BB/{iso}/{fileset_id}/metadata.json

Requirements:
    - api-cache/bibles/bibles_page_*.json (Bible catalog)
    - api-cache/samples/audio_timestamps_filesets.json (Timing data list)
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class IndependentCacheDataSorter:
    """Sort cache data independently - no stats/ dependencies."""

    def __init__(self, cache_dir: str = "api-cache", output_dir: str = "sorted/BB"):
        self.cache_dir = Path(cache_dir)
        self.bibles_dir = self.cache_dir / "bibles"
        self.output_dir = Path(output_dir)

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Data structures
        self.all_bibles = []
        self.timing_filesets = set()

        # Language data organized by ISO
        self.language_data = defaultdict(
            lambda: {
                "language_info": None,
                "audio_filesets": [],
                "text_filesets": [],
                "audio_details": [],
                "text_details": [],
            }
        )

        self.processed_filesets = set()

        # Exclusion tracking
        self.exclusions = {
            "sa_versions": [],  # Streaming-only Story Adaptations (SA suffix)
            "partial_content": [],  # Partial OT/NT (OTP, NTP, etc.)
            "story_adaptations": [],  # True story adaptations from video filesets
        }

    def load_timing_filesets(self):
        """Load the list of filesets that have timing data."""
        timing_file = self.cache_dir / "samples" / "audio_timestamps_filesets.json"
        if not timing_file.exists():
            print(f"Warning: {timing_file} not found")
            return

        with open(timing_file) as f:
            data = json.load(f)
            for item in data:
                self.timing_filesets.add(item["fileset_id"])

        print(f"Loaded {len(self.timing_filesets)} filesets with timing data")

    def load_all_bibles(self):
        """Load all Bible data from paginated cache files."""
        bible_files = sorted(self.bibles_dir.glob("bibles_page_*.json"))

        if not bible_files:
            print(f"Error: No Bible files found in {self.bibles_dir}")
            sys.exit(1)

        for bible_file in bible_files:
            with open(bible_file) as f:
                data = json.load(f)
                self.all_bibles.extend(data["data"])

        print(f"Loaded {len(self.all_bibles)} Bibles from {len(bible_files)} files")

    def normalize_fileset_id(self, fileset_id: str) -> str:
        """
        Remove suffixes like -opus16 to get base fileset ID.

        Examples:
            ENGWEBN1DA-opus16 → ENGWEBN1DA
            ENGWEBN1DA-mp3 → ENGWEBN1DA
        """
        suffixes = ["-opus16", "-opus32", "-mp3", "-64", "-128", "16"]
        for suffix in suffixes:
            if fileset_id.endswith(suffix):
                return fileset_id[: -len(suffix)]
        return fileset_id

    def filter_dramatized_versions(self, filesets: List[str]) -> List[str]:
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

    def match_audio_to_text(
        self, audio_fileset_id: str, text_filesets: List[str]
    ) -> List[str]:
        """
        Find text filesets that match an audio fileset by prefix comparison.

        Matching logic:
        - Compare first 7 characters of audio ID with text ID
        - If text ID is shorter than 7, use text ID length for comparison

        Examples:
            ENGWEBN1DA matches ENGWEB (first 6 chars)
            ENGWEBN1DA matches ENGWEBN_ET (first 7 chars)

        Args:
            audio_fileset_id: Audio fileset ID to match
            text_filesets: List of text fileset IDs to search

        Returns:
            List of matching text fileset IDs
        """
        if len(audio_fileset_id) < 6:
            return []

        matches = []
        for text_id in text_filesets:
            # Use minimum of 7 or text ID length
            compare_length = min(7, len(text_id))

            if len(audio_fileset_id) >= compare_length:
                if audio_fileset_id[:compare_length] == text_id[:compare_length]:
                    matches.append(text_id)

        return sorted(matches)

    def determine_book_set(self, fileset_id: str, size: str) -> str:
        """
        Determine book set from fileset structure and size field.

        Fileset ID structure (position 6, 0-indexed):
        - O = Old Testament
        - N = New Testament
        - C = Complete Bible
        - P = Partial
        - S = Story

        Size field values:
        - C, NTOTP = Complete Bible
        - NT, NTP = New Testament
        - OT, OTP = Old Testament

        Args:
            fileset_id: Fileset identifier
            size: Size field from fileset

        Returns:
            Book set category: FULL, OT, NT, PARTIAL, STORY, or VARIOUS
        """
        book_set = None

        # Check fileset ID structure (position 6)
        if len(fileset_id) >= 7:
            collection = fileset_id[6]
            if collection == "O":
                book_set = "OT"
            elif collection == "N":
                book_set = "NT"
            elif collection == "C":
                book_set = "FULL"
            elif collection == "P":
                book_set = "PARTIAL"
            elif collection == "S":
                book_set = "STORY"

        # Validate/enhance with size field, but respect PARTIAL collections
        # Don't override PARTIAL with OT/NT based on size alone
        if book_set == "PARTIAL":
            # Keep as PARTIAL - these are incomplete book sets
            pass
        elif size in ["C", "NTOTP"]:
            book_set = "FULL"
        elif size in ["NT", "NTP"]:
            if book_set not in ["OT", "FULL"]:
                book_set = "NT"
        elif size in ["OT", "OTP"]:
            if book_set not in ["NT", "FULL"]:
                book_set = "OT"

        return book_set or "VARIOUS"

    def organize_language_data(self):
        """
        Organize all bibles by language ISO code.
        Categorize filesets as audio or text.
        Store details for later analysis.
        """
        for bible in self.all_bibles:
            iso = bible.get("iso")
            if not iso:
                continue

            language_id = bible.get("language_id")
            language_name = bible.get("language")
            autonym = bible.get("autonym")

            # Store language info (first occurrence)
            if self.language_data[iso]["language_info"] is None:
                self.language_data[iso]["language_info"] = {
                    "iso": iso,
                    "language_id": language_id,
                    "name": language_name,
                    "autonym": autonym or "",
                }

            # Process filesets
            filesets = bible.get("filesets", {})
            for storage_key, fileset_list in filesets.items():
                for fileset in fileset_list:
                    fileset_id = fileset.get("id")
                    fileset_type = fileset.get("type", "")
                    size = fileset.get("size", "")

                    if not fileset_id:
                        continue

                    # Categorize and store
                    if fileset_type in [
                        "audio",
                        "audio_drama",
                        "audio_stream",
                        "audio_drama_stream",
                    ]:
                        if fileset_id not in self.language_data[iso]["audio_filesets"]:
                            self.language_data[iso]["audio_filesets"].append(fileset_id)
                            self.language_data[iso]["audio_details"].append(
                                {
                                    "fileset": fileset,
                                    "bible": bible,
                                    "book_set": self.determine_book_set(
                                        fileset_id, size
                                    ),
                                }
                            )
                    elif fileset_type.startswith("text"):
                        if fileset_id not in self.language_data[iso]["text_filesets"]:
                            self.language_data[iso]["text_filesets"].append(fileset_id)
                            self.language_data[iso]["text_details"].append(
                                {
                                    "fileset": fileset,
                                    "bible": bible,
                                    "book_set": self.determine_book_set(
                                        fileset_id, size
                                    ),
                                }
                            )

        print(f"Organized data for {len(self.language_data)} languages")

    def compute_syncable_pairs(self, iso: str) -> List[Dict]:
        """
        Compute which audio-text pairs are syncable for a language.

        A pair is syncable when:
        1. Audio does NOT have timing data already
        2. Audio matches text by prefix
        3. After filtering dramatized versions

        Args:
            iso: Language ISO code

        Returns:
            List of dictionaries with audio_fileset_id and text_fileset_id
        """
        lang_data = self.language_data[iso]
        audio_filesets = lang_data["audio_filesets"]
        text_filesets = lang_data["text_filesets"]

        # Filter out audio that already has timing
        audio_without_timing = [
            fs
            for fs in audio_filesets
            if self.normalize_fileset_id(fs) not in self.timing_filesets
        ]

        # Filter dramatized versions
        audio_filtered = self.filter_dramatized_versions(audio_without_timing)

        # Match to text
        syncable_pairs = []
        for audio_id in audio_filtered:
            matching_text = self.match_audio_to_text(audio_id, text_filesets)
            if matching_text:
                syncable_pairs.append(
                    {
                        "audio_fileset_id": audio_id,
                        "text_fileset_id": matching_text,
                    }
                )

        return syncable_pairs

    def determine_data_source(
        self, fileset_id: str, is_audio: bool, syncable_pairs: List[Dict]
    ) -> Optional[str]:
        """
        Determine data source category for a fileset.

        Categories:
        - "timing": Audio has timing data
        - "sync": Audio can be synced with text (no timing yet)
        - None: Not categorized

        Args:
            fileset_id: Fileset identifier
            is_audio: Whether this is an audio fileset
            syncable_pairs: List of syncable pairs for this language

        Returns:
            Data source string or None
        """
        if not is_audio:
            # Check if this text is part of a syncable pair
            for pair in syncable_pairs:
                if fileset_id in pair["text_fileset_id"]:
                    return "sync"
            return None

        # Check timing availability
        normalized = self.normalize_fileset_id(fileset_id)
        if normalized in self.timing_filesets:
            return "timing"

        # Check if syncable
        for pair in syncable_pairs:
            if pair["audio_fileset_id"] == fileset_id:
                return "sync"

        return None

    def is_syncable(self, fileset_id: str, syncable_pairs: List[Dict]) -> bool:
        """
        Check if this audio fileset is part of a syncable pair.

        Args:
            fileset_id: Audio fileset identifier
            syncable_pairs: List of syncable pairs

        Returns:
            True if syncable, False otherwise
        """
        for pair in syncable_pairs:
            if pair["audio_fileset_id"] == fileset_id:
                return True
        return False

    def create_metadata(
        self, iso: str, fileset_detail: Dict, syncable_pairs: List[Dict]
    ) -> Dict:
        """
        Create comprehensive metadata for a fileset.

        Args:
            iso: Language ISO code
            fileset_detail: Dictionary with fileset, bible, and book_set
            syncable_pairs: List of syncable pairs for this language

        Returns:
            Complete metadata dictionary
        """
        fileset = fileset_detail["fileset"]
        bible = fileset_detail["bible"]
        book_set = fileset_detail["book_set"]

        fileset_id = fileset.get("id", "")
        fileset_type = fileset.get("type", "")

        is_audio = fileset_type in [
            "audio",
            "audio_drama",
            "audio_stream",
            "audio_drama_stream",
        ]
        is_text = fileset_type.startswith("text")

        # Get syncable pairs for this fileset
        audio_text_pairs = []
        if is_audio and self.is_syncable(fileset_id, syncable_pairs):
            for pair in syncable_pairs:
                if pair["audio_fileset_id"] == fileset_id:
                    audio_text_pairs.append(pair)

        # Check timing availability
        has_timing = self.normalize_fileset_id(fileset_id) in self.timing_filesets

        metadata = {
            "language": self.language_data[iso]["language_info"],
            "bible": {
                "abbr": bible.get("abbr", ""),
                "name": bible.get("name", ""),
            },
            "fileset": {
                "id": fileset_id,
                "type": fileset_type,
                "size": fileset.get("size", ""),
                "volume": fileset.get("volume", ""),
                "date": bible.get("date") or fileset.get("date") or "",
            },
            "categorization": {
                "has_text": is_text,
                "has_audio": is_audio,
                "has_timing": has_timing,
                "data_source": self.determine_data_source(
                    fileset_id, is_audio, syncable_pairs
                ),
                "book_set": book_set,
                "syncable": self.is_syncable(fileset_id, syncable_pairs),
                "audio_text_pairs": audio_text_pairs,
            },
            "download_ready": {
                "text_fileset": fileset_id if is_text else None,
                "audio_fileset": fileset_id if is_audio else None,
                "timing_available": has_timing,
            },
        }

        # Add collection info if available (position 6 in fileset ID)
        if len(fileset_id) >= 7:
            collection = fileset_id[6]
            metadata["fileset"]["collection"] = collection

        return metadata

    def track_exclusions(
        self,
        iso: str,
        bible: Dict,
        fileset: Dict,
        fileset_id: str,
        fileset_type: str,
        book_set: str,
    ):
        """
        Track filesets that should be excluded from download attempts.

        Categories:
        1. SA versions - Streaming-only Story Adaptations (SA suffix in fileset ID)
        2. Partial content - Incomplete testaments (OTP, NTP, PARTIAL book_set)
        3. Story adaptations - Video-based story adaptations
        """
        # 1. Check for SA (Story Adaptation) - streaming-only audio
        if "SA" in fileset_id and len(fileset_id) >= 10:
            # SA typically appears in positions 7-10 (e.g., N1SA, N2SA, O1SA, O2SA)
            if fileset_id[7:10].endswith("SA") or fileset_id[8:10] == "SA":
                self.exclusions["sa_versions"].append(
                    {
                        "iso": iso,
                        "language": bible.get("language", ""),
                        "bible_abbr": bible.get("abbr", ""),
                        "bible_name": bible.get("name", ""),
                        "fileset_id": fileset_id,
                        "type": fileset_type,
                        "size": fileset.get("size", ""),
                        "reason": "Streaming-only Story Adaptation (SA suffix)",
                    }
                )

        # 2. Check for partial content (only PARTIAL book_set from collection "P")
        # Note: OTP/NTP are kept as OT/NT so they work for books they contain
        if book_set == "PARTIAL":
            self.exclusions["partial_content"].append(
                {
                    "iso": iso,
                    "language": bible.get("language", ""),
                    "bible_abbr": bible.get("abbr", ""),
                    "bible_name": bible.get("name", ""),
                    "fileset_id": fileset_id,
                    "type": fileset_type,
                    "size": fileset.get("size", ""),
                    "book_set": book_set,
                    "reason": "Partial content (collection P - incomplete book set)",
                }
            )

        # 3. Check for story adaptations from video filesets
        if "story" in fileset_type.lower() or "video" in fileset_type.lower():
            self.exclusions["story_adaptations"].append(
                {
                    "iso": iso,
                    "language": bible.get("language", ""),
                    "bible_abbr": bible.get("abbr", ""),
                    "bible_name": bible.get("name", ""),
                    "fileset_id": fileset_id,
                    "type": fileset_type,
                    "size": fileset.get("size", ""),
                    "reason": "Video/Story adaptation format",
                }
            )

    def save_metadata(self, iso: str, fileset_id: str, metadata: Dict):
        """
        Save metadata to the appropriate directory.

        Args:
            iso: Language ISO code
            fileset_id: Fileset identifier
            metadata: Metadata dictionary to save
        """
        output_path = self.output_dir / iso / fileset_id
        output_path.mkdir(parents=True, exist_ok=True)

        metadata_file = output_path / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def process_all_languages(self):
        """
        Process all languages and create sorted directory structure.

        For each language:
        1. Compute syncable pairs
        2. Create metadata for each fileset
        3. Save to sorted/{iso}/{fileset_id}/metadata.json
        """
        processed_count = 0

        for iso, lang_data in self.language_data.items():
            # Compute syncable pairs for this language
            syncable_pairs = self.compute_syncable_pairs(iso)

            # Process audio filesets
            for audio_detail in lang_data["audio_details"]:
                fileset_id = audio_detail["fileset"]["id"]

                fileset_key = f"{iso}/{fileset_id}"
                if fileset_key in self.processed_filesets:
                    continue

                self.processed_filesets.add(fileset_key)

                metadata = self.create_metadata(iso, audio_detail, syncable_pairs)
                self.save_metadata(iso, fileset_id, metadata)

                # Track exclusions
                bible = audio_detail.get("bible", {})
                fileset = audio_detail.get("fileset", {})
                fileset_type = fileset.get("type", "")
                book_set = metadata["categorization"]["book_set"]
                self.track_exclusions(
                    iso, bible, fileset, fileset_id, fileset_type, book_set
                )

                processed_count += 1

            # Process text filesets
            for text_detail in lang_data["text_details"]:
                fileset_id = text_detail["fileset"]["id"]

                fileset_key = f"{iso}/{fileset_id}"
                if fileset_key in self.processed_filesets:
                    continue

                self.processed_filesets.add(fileset_key)

                metadata = self.create_metadata(iso, text_detail, syncable_pairs)
                self.save_metadata(iso, fileset_id, metadata)

                # Track exclusions
                bible = text_detail.get("bible", {})
                fileset = text_detail.get("fileset", {})
                fileset_type = fileset.get("type", "")
                book_set = metadata["categorization"]["book_set"]
                self.track_exclusions(
                    iso, bible, fileset, fileset_id, fileset_type, book_set
                )

                processed_count += 1

            if processed_count % 1000 == 0:
                print(f"Processed {processed_count} filesets...")

        print(f"\nProcessing complete:")
        print(f"  - Processed: {processed_count} filesets")
        print(f"  - Languages: {len(self.language_data)}")
        print(f"  - Output directory: {self.output_dir}")

        # Save exclusion data
        self.save_exclusions()

    def save_exclusions(self):
        """Save exclusion data to sorted/BB/exclude_download.json."""
        exclusion_file = self.output_dir / "exclude_download.json"

        # Create summary statistics
        summary = {
            "generated": datetime.now().isoformat(),
            "summary": {
                "sa_versions": len(self.exclusions["sa_versions"]),
                "partial_content": len(self.exclusions["partial_content"]),
                "story_adaptations": len(self.exclusions["story_adaptations"]),
                "total_excluded": sum(len(v) for v in self.exclusions.values()),
            },
            "exclusions": self.exclusions,
        }

        with open(exclusion_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"\nExclusion tracking:")
        print(
            f"  - SA versions (streaming-only): {len(self.exclusions['sa_versions'])}"
        )
        print(
            f"  - Partial content (OTP/NTP): {len(self.exclusions['partial_content'])}"
        )
        print(
            f"  - Story adaptations (video): {len(self.exclusions['story_adaptations'])}"
        )
        print(f"  - Total excluded: {sum(len(v) for v in self.exclusions.values())}")
        print(f"  - Saved to: {exclusion_file}")

    def generate_summary(self):
        """Generate a summary of what was sorted."""
        summary = {
            "total_languages": len(self.language_data),
            "total_filesets": len(self.processed_filesets),
            "timing_filesets_available": len(self.timing_filesets),
        }

        # Count by category
        syncable_count = 0
        timing_count = 0
        audio_count = 0
        text_count = 0

        for iso, lang_data in self.language_data.items():
            syncable_pairs = self.compute_syncable_pairs(iso)
            syncable_count += len(syncable_pairs)

            for audio_detail in lang_data["audio_details"]:
                audio_count += 1
                fileset_id = audio_detail["fileset"]["id"]
                if self.normalize_fileset_id(fileset_id) in self.timing_filesets:
                    timing_count += 1

            text_count += len(lang_data["text_details"])

        summary["syncable_pairs"] = syncable_count
        summary["filesets_with_timing"] = timing_count
        summary["audio_filesets"] = audio_count
        summary["text_filesets"] = text_count

        summary_file = self.output_dir / "summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"\nSummary:")
        print(f"  - Total languages: {summary['total_languages']}")
        print(f"  - Total filesets: {summary['total_filesets']}")
        print(f"  - Audio filesets: {summary['audio_filesets']}")
        print(f"  - Text filesets: {summary['text_filesets']}")
        print(f"  - Syncable pairs: {summary['syncable_pairs']}")
        print(f"  - With timing: {summary['filesets_with_timing']}")

    def run(self):
        """Run the complete sorting process - FULLY INDEPENDENT."""
        print("=" * 70)
        print("INDEPENDENT Cache Data Sorter")
        print("=" * 70)
        print()
        print("✓ NO dependency on stats/ directory")
        print("✓ Direct transformation: api-cache/ → sorted/")
        print("✓ All categorization computed on-the-fly")
        print()

        print("Step 1: Loading timing filesets...")
        self.load_timing_filesets()

        print("\nStep 2: Loading all Bibles...")
        self.load_all_bibles()

        print("\nStep 3: Organizing by language...")
        self.organize_language_data()

        print("\nStep 4: Processing and creating metadata...")
        self.process_all_languages()

        print("\nStep 5: Generating summary...")
        self.generate_summary()

        print("\n" + "=" * 70)
        print("✓ Independent sorting complete!")
        print("=" * 70)
        print()
        print("All categorization was computed directly from api-cache.")
        print("No stats/ files were used or required.")
        print()
        print(f"Output: {self.output_dir}/")


def main():
    sorter = IndependentCacheDataSorter()
    sorter.run()


if __name__ == "__main__":
    main()
