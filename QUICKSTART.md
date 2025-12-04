# Quick Start Guide - Bible Story Builder

Build multilingual Bible stories in minutes!

## What is Bible Story Builder?

Bible Story Builder helps you create Bible stories in multiple languages by downloading text, audio, and timing data from the Digital Bible Platform. Perfect for:
- Literacy programs
- Oral Bible storytelling
- Translation projects
- Multilingual ministry
- Bible teaching materials

## Prerequisites

- Python 3.7+
- Internet connection
- Digital Bible Platform API key

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get API Key

Get your free API key from [https://www.biblebrain.com/](https://www.biblebrain.com/)

### 3. Set Environment Variable

```bash
export DBP_API_KEY="your-api-key-here"
```

Or create a `.env` file:
```
DBP_API_KEY=your-api-key-here
```

## Building Your First Story

### Step 1: Define Your Story

Edit `config/story-set.conf` to define which Bible passages make up your story:

```
# My first story - Creation
Creation_Story
GEN:1-3

# Christmas story
Christmas_Story
LUK:1:26-56,LUK:2:1-40,MAT:2:1-23

# Easter story
Easter_Story
MAT:26-28,LUK:24,JHN:20
```

Format:
- Story name on first line
- Bible references on second line (comma-separated)
- Blank line between stories

### Step 2: Choose Your Languages

Edit `config/regions.conf` to specify which languages you want:

```
# African languages
My_Africa_Languages
swa,yor,amh,som,hau

# Asian languages  
My_Asia_Languages
hin,ben,tam,tel,vie

# European languages
My_Europe_Languages
eng,spa,fra,deu,por
```

Format:
- Region/group name on first line
- Language ISO codes on second line (comma-separated)
- Blank line between regions

### Step 3: Fetch Bible Catalog

First time only - download the Bible catalog:

```bash
python3 fetch_api_cache.py
```

This downloads information about 2000+ languages and 12,000+ Bible versions. Takes 2-5 minutes.

### Step 4: Organize Metadata

Process the catalog data:

```bash
python3 sort_cache_data.py
```

This organizes the data by language. Takes 1-2 minutes.

### Step 5: Download Your Story

Now download your story in multiple languages:

```bash
python3 download_language_content.py --region My_Africa_Languages --books Creation_Story
```

This downloads the Creation story (Genesis 1-3) in Swahili, Yoruba, Amharic, Somali, and Hausa!

## Output

Your story content is organized like this:

```
downloads/BB/
├── swa/                    # Swahili
│   └── SWAHAU/            # Bible version
│       └── GEN/           # Book
│           ├── GEN_001_SWAHAU2N2DA.mp3          # Audio
│           ├── GEN_001_SWAHAU2TP.txt            # Text
│           ├── GEN_001_SWAHAU2N2DA_timing.json  # Timing
│           ├── GEN_002_SWAHAU2N2DA.mp3
│           ├── GEN_002_SWAHAU2TP.txt
│           └── GEN_003_SWAHAU2N2DA.mp3
├── yor/                    # Yoruba
│   └── YORBSN/
│       └── GEN/
└── amh/                    # Amharic
    └── AMHBSN/
        └── GEN/
```

Each language folder contains:
- **Audio files** (.mp3) - Narrated Bible text
- **Text files** (.txt) - Bible text in that language
- **Timing files** (.json) - Word-by-word timing for synchronization

## Common Use Cases

### Literacy Program

Build simple stories for new readers:

```bash
# 1. Define short, easy stories
# config/story-set.conf:
Beginner_Stories
RUT:1-4,JON:1-4,PSA:23

# 2. Download for your language
python3 download_language_content.py swa --books Beginner_Stories
```

### Oral Storytelling

Get audio for narrative passages:

```bash
# 1. Define narrative stories
# config/story-set.conf:
Storytelling_Set
GEN:1-3,GEN:6-9,GEN:37-50,EXO:1-15,JDG:6-7,RUT:1-4,1SA:17

# 2. Download for multiple languages
python3 download_language_content.py --region West_Africa --books Storytelling_Set
```

### Jesus Film Content

Get gospel stories with timing data:

```bash
# 1. Define Jesus stories
# config/story-set.conf:
Jesus_Film
MAT:1-2,LUK:1-2,JHN:1-3,MAT:5-7,JHN:11,MAT:26-28,ACT:1-2

# 2. Download with timing (for video sync)
python3 download_language_content.py --book-set TIMING_NT --books Jesus_Film
```

### Multi-language Bible App

Build comprehensive story arc:

```bash
# 1. Define full story arc
# config/story-set.conf:
Bible_Story_Arc
GEN:1-3,GEN:6-9,GEN:12,GEN:22,EXO:12,EXO:20,MAT:1-2,LUK:2,JHN:3,MAT:26-28,ACT:1-2

# 2. Download for primary languages
python3 download_language_content.py --region Primary_Languages --books Bible_Story_Arc
```

## Story Set Examples

Here are proven story sets you can use:

### Old Testament Highlights
```
OT_Highlights
GEN:1-3,GEN:6-9,GEN:12,GEN:22,EXO:1-15,EXO:20,JOS:2,JDG:6-7,RUT:1-4,1SA:17,2SA:11-12,1KI:18,EST:1-10,JOB:1-2,PSA:23,PSA:51,ISA:53,DAN:1-6,JON:1-4
```

### New Testament Highlights
```
NT_Highlights
MAT:1-2,MAT:5-7,MAT:13,MAT:26-28,MRK:1,LUK:2,LUK:10,LUK:15,LUK:24,JHN:1,JHN:3,JHN:11,JHN:14-17,JHN:20,ACT:1-2,ACT:9,ROM:8,1CO:13,EPH:2,REV:21-22
```

### Creation to Christ
```
CREATION_TO_CHRIST
GEN:1-3,GEN:6-9,GEN:12,GEN:22,EXO:12,EXO:20,MAT:1-2,LUK:2:1-40,JHN:1:1-18,JHN:3:1-21,MAT:26-28,LUK:24,ACT:1-2,REV:21-22
```

### Complete Gospels
```
Four_Gospels
MAT:1-28,MRK:1-16,LUK:1-24,JHN:1-21
```

## Advanced Options

### Download Specific Language
```bash
python3 download_language_content.py eng --books Creation_Story
```

### Download Multiple Stories
```bash
python3 download_language_content.py --region Africa --books Creation_Story,Easter_Story,Christmas_Story
```

### Combine Filters
```bash
# Only languages with audio+text sync, in Africa region
python3 download_language_content.py --book-set SYNC_NT --region Africa --books Jesus_Film
```

### Force Re-download
```bash
python3 download_language_content.py eng --books Creation_Story --force
```

### Batch Processing
Create `languages.txt`:
```
eng
spa
fra
por
```

Download:
```bash
python3 download_language_content.py --batch languages.txt --books Creation_Story
```

## Book Code Reference

Use these codes in your story sets:

**Old Testament**: GEN, EXO, LEV, NUM, DEU, JOS, JDG, RUT, 1SA, 2SA, 1KI, 2KI, 1CH, 2CH, EZR, NEH, EST, JOB, PSA, PRO, ECC, SNG, ISA, JER, LAM, EZK, DAN, HOS, JOL, AMO, OBA, JON, MIC, NAM, HAB, ZEP, HAG, ZEC, MAL

**New Testament**: MAT, MRK, LUK, JHN, ACT, ROM, 1CO, 2CO, GAL, EPH, PHP, COL, 1TH, 2TH, 1TI, 2TI, TIT, PHM, HEB, JAS, 1PE, 2PE, 1JN, 2JN, 3JN, JUD, REV

## Chapter Specification

- **Full book**: `GEN` (all chapters)
- **Single chapter**: `GEN:1`
- **Chapter range**: `GEN:1-3` (chapters 1, 2, 3)
- **Multiple chapters**: `PSA:1,23,91` (chapters 1, 23, 91)
- **Verse ranges**: `JHN:3:1-21` (John 3:1-21)
- **Multiple books**: `GEN:1-3,EXO:1-5,MAT:1-2`

## Troubleshooting

### No content downloaded
- **Check API key**: `echo $DBP_API_KEY`
- **Verify story set name**: Check spelling in config/story-set.conf
- **Verify region name**: Check spelling in config/regions.conf
- **Check metadata exists**: `ls sorted/BB/*_metadata.json`

### Download errors
- **View errors**: `cat download_log/{language}_errors.json`
- **Most common**: "content not available" (API doesn't have it)
- **Actual failures**: Very rare (< 1%)

### Missing metadata
Run setup steps again:
```bash
python3 fetch_api_cache.py    # Re-fetch catalog
python3 sort_cache_data.py     # Re-organize
```

### Need fresh data
```bash
# Update to latest Bible catalog
python3 fetch_api_cache.py
python3 sort_cache_data.py
```

### Language not downloading
- Check if language has content: `cat sorted/BB/{iso}_metadata.json`
- Check if language has content in sorted metadata
- Try different Bible books if specific books aren't available

## Workflow Summary

```
┌─────────────────────────────────────────┐
│ 1. Define Story (story-set.conf)       │
│    Creation_Story                       │
│    GEN:1-3                              │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ 2. Choose Languages (regions.conf)     │
│    My_Languages                         │
│    swa,yor,amh                          │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ 3. Fetch API Data (once)               │
│    python3 fetch_api_cache.py          │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ 4. Organize Metadata (once)            │
│    python3 sort_cache_data.py          │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ 5. Download Story                       │
│    python3 download_language_content.py │
│    --region My_Languages                │
│    --books Creation_Story               │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ 6. Use Your Content!                    │
│    downloads/BB/{language}/...          │
└─────────────────────────────────────────┘
```

## Coming Soon: Web App Generation

Bible Story Builder will soon generate ready-to-use web apps from your stories with:
- Automatic language switching
- Audio synchronized with text
- Responsive design
- Offline support

See [ROADMAP.md](ROADMAP.md) for details.

## Next Steps

- Explore [README.md](README.md) for advanced features
- Check [ERROR_LOGGING_QUICKREF.md](ERROR_LOGGING_QUICKREF.md) for error details
- Review example story sets in `config/story-set.conf`
- Customize regions in `config/regions.conf`

## Getting Help

- Check error logs: `download_log/{language}_errors.json`
- View language metadata: `sorted/BB/{language}_metadata.json`
- Get help: `python3 download_language_content.py --help`

## Tips for Success

1. **Start small**: Test with 1-2 languages first
2. **Use tested stories**: Start with provided story sets
3. **Verify configuration**: Story set and region names match config files
4. **Be patient**: First fetch takes a few minutes
5. **Verify output**: Check downloads/BB/ for your files

Happy story building! 🎉