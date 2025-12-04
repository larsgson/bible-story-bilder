# Error Logging Quick Reference

## Overview
The error logging system tracks download failures with detailed, format-specific information. Errors are separated by content type (audio, text, timing) to provide clear insights into what failed and why.

## Error Log Structure

```json
{
  "language": "iso",
  "last_updated": "2024-01-01T00:00:00",
  "errors": [
    {
      "timestamp": "2024-01-01T00:00:00",
      "book": "GEN",
      "chapter": 1,
      "audio_errors": [
        {
          "timestamp": "2024-01-01T00:00:00",
          "error_type": "no_audio_available",
          "fileset": "XXXNNN2DA",
          "distinct_id": "XXXNNN",
          "format": "mp3",
          "details": "No audio path returned for fileset XXXNNN2DA"
        }
      ],
      "text_errors": [...],
      "timing_errors": [...]
    }
  ]
}
```

## Error Types

### Audio Errors
- `no_audio_available` - API returned no audio URL
- `audio_download_failed` - Failed to download or save audio file

### Text Errors
- `no_text_available` - API returned no text content
- `text_save_failed` - Failed to save text file

### Timing Errors
- `no_timing_available` - API returned no timing data
- `timing_save_failed` - Failed to save timing file

## Key Fields

| Field | Description | Present In |
|-------|-------------|------------|
| `timestamp` | When error occurred | All |
| `error_type` | Type of error | All |
| `fileset` | Fileset ID that failed | All |
| `distinct_id` | Bible version identifier | All |
| `format` | Audio format (mp3, opus, etc.) | Audio only |
| `details` | Human-readable description | All |

## Programmatic Access

### Load Error Log
```python
import json
from pathlib import Path

error_file = Path("download_log/eng_errors.json")
with open(error_file) as f:
    data = json.load(f)
```

### Get Error Summary
```python
from download_language_content import get_error_summary

summary = get_error_summary("eng")
print(f"Chapters with errors: {summary['total_chapters_with_errors']}")
print(f"Audio errors: {summary['audio_errors']}")
print(f"Text errors: {summary['text_errors']}")
print(f"Timing errors: {summary['timing_errors']}")
```

## Important Notes

1. **Only failures are logged** - Successful downloads don't appear in error logs
2. **Multiple format attempts** - If format 1 fails but format 2 succeeds, only format 1 failure is logged
3. **Timing is separate** - Timing errors are kept separate from audio errors even though timing depends on audio
4. **Per-chapter grouping** - All errors for a chapter are grouped together
5. **Empty arrays** - Content types with no errors show empty arrays `[]`

## Example Scenarios

### Scenario 1: Audio Format Fallback
- Try mp3 format → FAILS (logged in `audio_errors`)
- Try opus format → SUCCEEDS (not logged)
- Result: Only mp3 failure appears in error log

### Scenario 2: Audio Success, Timing Failure
- Download audio → SUCCEEDS (not logged)
- Download timing → FAILS (logged in `timing_errors`)
- Result: Timing error separate from audio

### Scenario 3: Multiple Content Type Failures
- Audio format 1 → FAILS (logged in `audio_errors`)
- Text format 1 → FAILS (logged in `text_errors`)
- Result: Both errors tracked in same chapter entry but different arrays

## Interpreting Error Logs

### High Audio Errors
- May indicate format availability issues
- Check if specific formats (mp3 vs opus) are more problematic
- Verify filesets are downloadable (not streaming-only)

### High Text Errors
- May indicate incomplete text filesets
- Check if specific Bible versions lack text

### High Timing Errors
- Timing data is optional/rare
- Not all filesets have timing data
- Usually not a critical issue

## Location

- Error logs: `download_log/{iso}_errors.json`
- Main script: `download_language_content.py`

## Manual Analysis

You can manually inspect error logs using standard JSON tools:

```bash
# View error log for a specific language
cat download_log/eng_errors.json | python3 -m json.tool

# Count languages with errors
ls download_log/*_errors.json | wc -l

# Search for specific error types
grep -r "audio_download_failed" download_log/

# List all languages with errors
ls download_log/*_errors.json | sed 's/.*\///; s/_errors.json//'
```
