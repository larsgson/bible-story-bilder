#!/usr/bin/env python3
"""
Compare old incomplete-timecode category with new categorization logic.
This helps verify that the migration from incomplete-timecode to audio-with-timecode
and with-timecode is correct.
"""

import json
from collections import defaultdict
from pathlib import Path

WORKSPACE_DIR = Path("workspace")


def analyze_old_incomplete_timecode():
    """
    Analyze what's in the old incomplete-timecode folders and show what
    category they should be in with the new logic.
    """
    print("=" * 80)
    print("ANALYZING OLD incomplete-timecode CATEGORY")
    print("=" * 80)
    print("\nThis shows what the old 'incomplete-timecode' contained and")
    print("what category each language should be in with the new logic.\n")

    found_any = False
    categorization = defaultdict(list)

    for canon_dir in sorted(WORKSPACE_DIR.iterdir()):
        if not canon_dir.is_dir():
            continue

        canon = canon_dir.name
        old_category_dir = canon_dir / "incomplete-timecode"

        if not old_category_dir.exists() or not old_category_dir.is_dir():
            continue

        found_any = True
        print(f"\n{canon.upper()}/incomplete-timecode:")
        print("-" * 80)

        iso_dirs = sorted([d for d in old_category_dir.iterdir() if d.is_dir()])

        if not iso_dirs:
            print("  (empty)")
            continue

        for iso_dir in iso_dirs:
            iso = iso_dir.name

            # Find the data.json file
            data_files = list(iso_dir.glob("*/data.json"))

            if not data_files:
                print(f"  ? {iso}: No data.json found")
                continue

            # Read the data.json file
            data_file = data_files[0]
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check what filesets exist
            filesets = data.get("filesets", {})

            has_audio = any(fs for fs in filesets.get("audio", {}).values() if fs)
            has_text = any(fs for fs in filesets.get("text", {}).values() if fs)
            has_timing = any(fs for fs in filesets.get("timing", {}).values() if fs)

            # Determine correct category with new logic
            if has_audio and has_text and has_timing:
                correct_category = "with-timecode"
                symbol = "→"
            elif has_audio and has_timing and not has_text:
                correct_category = "audio-with-timecode"
                symbol = "→"
            elif has_audio and has_text:
                correct_category = "syncable"
                symbol = "⚠"
            elif has_text:
                correct_category = "text-only"
                symbol = "⚠"
            elif has_audio:
                correct_category = "audio-only"
                symbol = "⚠"
            else:
                correct_category = "failed"
                symbol = "✗"

            categorization[correct_category].append((canon, iso))

            # Show what filesets exist
            audio_info = ""
            text_info = ""
            timing_info = ""

            if has_audio:
                audio_filesets = [fs for fs in filesets.get("audio", {}).values() if fs]
                audio_info = f"audio={audio_filesets[0] if audio_filesets else '[]'}"

            if has_text:
                text_filesets = [fs for fs in filesets.get("text", {}).values() if fs]
                text_info = f"text={text_filesets[0] if text_filesets else '[]'}"

            if has_timing:
                timing_filesets = [
                    fs for fs in filesets.get("timing", {}).values() if fs
                ]
                timing_info = (
                    f"timing={timing_filesets[0] if timing_filesets else '[]'}"
                )

            content_str = ", ".join(filter(None, [audio_info, text_info, timing_info]))

            print(f"  {symbol} {iso:8s} → {correct_category:20s} ({content_str})")

    if not found_any:
        print("\n✓ No old 'incomplete-timecode' directories found.")
        print("  The workspace has been cleaned up or never had the old structure.")
        return

    # Summary by new category
    print("\n" + "=" * 80)
    print("SUMMARY: Where old incomplete-timecode languages should go")
    print("=" * 80)

    for category in [
        "with-timecode",
        "audio-with-timecode",
        "syncable",
        "text-only",
        "audio-only",
        "failed",
    ]:
        if category in categorization:
            langs = categorization[category]
            print(f"\n{category}: {len(langs)} languages")
            for canon, iso in langs[:5]:  # Show first 5
                print(f"  - {canon}/{iso}")
            if len(langs) > 5:
                print(f"  ... and {len(langs) - 5} more")

    print("\n" + "=" * 80)
    print("EXPECTED RESULTS:")
    print("=" * 80)
    print("✓ Most should go to: with-timecode (audio + text + timing)")
    print("✓ Some should go to: audio-with-timecode (audio + timing only)")
    print("⚠ If any go to syncable/text-only/audio-only: these were miscategorized")
    print("✗ If any go to failed: missing critical data")
    print("\nThe old 'incomplete-timecode' name was misleading because it included")
    print("languages with complete audio+text+timing, which should be 'with-timecode'.")


def analyze_new_structure():
    """
    Show what's currently in the new category structure.
    """
    print("\n\n" + "=" * 80)
    print("CURRENT CATEGORY DISTRIBUTION")
    print("=" * 80)

    categories_found = defaultdict(lambda: defaultdict(int))

    for canon_dir in sorted(WORKSPACE_DIR.iterdir()):
        if not canon_dir.is_dir():
            continue

        canon = canon_dir.name

        for category_dir in sorted(canon_dir.iterdir()):
            if not category_dir.is_dir():
                continue

            category = category_dir.name
            iso_count = len([d for d in category_dir.iterdir() if d.is_dir()])

            if iso_count > 0:
                categories_found[canon][category] = iso_count

    for canon in sorted(categories_found.keys()):
        print(f"\n{canon.upper()}:")
        for category in sorted(categories_found[canon].keys()):
            count = categories_found[canon][category]
            print(f"  {category:25s}: {count:4d} languages")

    print("\n" + "=" * 80)
    print("To fix the categorization, run: python sort_cache_data.py")
    print("=" * 80)


if __name__ == "__main__":
    analyze_old_incomplete_timecode()
    analyze_new_structure()
