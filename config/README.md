# Configuration Files

## regions.conf

Define geographic regions for filtering downloads.

### Format

```
RegionName
iso1,iso2,iso3

AnotherRegion
iso4,iso5,iso6
```

- Region names on their own line
- Language codes (ISO 639-3) on following lines, comma-separated
- Blank lines separate regions
- Comments start with `#`

### Usage

```bash
# List regions
python list_regions.py

# Download by region
python download_language_content.py --region Finland --books MAT:1
```

### Adding Regions

Edit `config/regions.conf` and add:

```
MyRegion
eng,spa,fra
```

Changes take effect immediately.

## story-set.conf

Define reusable book collections.

### Format

```
StorySetName
BOOK:CHAPTER,BOOK:CHAPTER

AnotherSet
BOOK:CHAPTER
```

- Story set names on their own line
- Book references on following lines, comma-separated
- Format: `BOOK:CHAPTER` (e.g., `GEN:1`, `PSA:117`)
- Blank lines separate story sets
- Comments start with `#`

### Usage

```bash
# Download story set
python download_language_content.py --books Test
python download_language_content.py eng --books Test
```

### Adding Story Sets

Edit `config/story-set.conf` and add:

```
Gospels
MAT:1-28,MRK:1-16,LUK:1-24,JHN:1-21

Creation
GEN:1-3
```

Changes take effect immediately.

## Common Language Codes

- `eng` - English
- `spa` - Spanish
- `fra` - French
- `deu` - German
- `por` - Portuguese
- `cmn` - Chinese (Mandarin)
- `hin` - Hindi
- `ara` - Arabic
- `rus` - Russian
- `jpn` - Japanese

Find all available languages:
```bash
ls sorted/
```
