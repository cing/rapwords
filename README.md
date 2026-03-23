# RapWords

Prepare Instagram Reel content from hip-hop vocabulary — short video clips from YouTube music videos with karaoke-style subtitle overlays highlighting featured vocabulary words.

Originally a [Tumblr blog](https://rapwords.tumblr.com/) and [PyCon Canada 2016 talk](archive/RapWordsTalk.ipynb).

## Prerequisites

- Python 3.10+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for video downloads
- [ffmpeg](https://ffmpeg.org/) built with libass for subtitle rendering
- `GENIUS_API_TOKEN` env var for discovering new content (free at https://genius.com/api-clients)

## Install

```bash
pip install -e .
```

## Usage

```bash
# Scrape historical blog posts from rapwords.tumblr.com
rapwords scrape

# List all posts (use --flagged or --usable to filter)
rapwords list
rapwords list --usable

# Show a specific post
rapwords show 1

# Find where lyrics appear in a YouTube video using auto-captions
rapwords find-time 1

# Download a YouTube video for a post
rapwords download 1

# Process a post into an Instagram-ready video
rapwords process 1 --start-time 01:23 --duration 20

# Look up all definitions for a word
rapwords lookup bespoke
rapwords lookup bespoke --context "before he speak his suit bespoke"
```

### Process options

| Option | Default | Effect |
|---|---|---|
| `--crop/--no-crop` | on | Crop to fill 9:16 (off = pad with black bars) |
| `--theme` | yellow | Lyrics color theme: `yellow`, `pink`, or `ice` |
| `--watermark` | white | Logo watermark: `white`, `black`, or `none` |
| `--watermark-scale` | 0.7 | Watermark size multiplier |
| `--static/--no-static` | on | TV static outro with hard cut and white noise |
| `--ass-file` | — | Use a manually edited `.ass` subtitle file |
| `--attribution/--no-attribution` | off | Show artist/song text overlay |

To fine-tune subtitle timings: process once to generate the `.ass` file in `data/output/`, edit it, then re-render with `--ass-file`.

## Discovering new content

Scan modern hip-hop lyrics from Genius for "big words" — rare vocabulary found in the Scrabble dictionary with low frequency in common English usage.

```bash
# Scan a specific song
rapwords discover --artist "Kendrick Lamar" --song "HUMBLE."

# Scan an artist's top songs
rapwords discover --artist "Aesop Rock" --max-songs 10

# Auto-add all discovered words without prompting
rapwords discover --artist "MF DOOM" --auto

# Stricter filtering: only rarer, longer words
rapwords discover --artist "Aesop Rock" --max-freq 100000 --min-length 7
```

For each big word found, the pipeline:
1. Extracts the surrounding bars (grouped by rhyming end-words)
2. Fetches a definition from the Free Dictionary API
3. Finds the official YouTube music video

Discovered posts are saved to `data/posts.json` and work with the full `download` → `find-time` → `process` workflow.

| Option | Default | Effect |
|---|---|---|
| `--max-freq` | 400,000 | Max word frequency — lower = rarer words only |
| `--min-length` | 5 | Minimum word length |
| `--max-songs` | 20 | Songs to scan when no `--song` given |
| `--auto` | off | Skip interactive selection, add all |

## Editing posts

```bash
# Update the YouTube video for a post (resets download state)
rapwords edit 1 --youtube-url "https://youtube.com/watch?v=NEW_ID"

# Change artist or song title
rapwords edit 1 --artist "2Pac" --song "I Ain't Mad at Cha"

# Replace lyrics (use | to separate lines)
rapwords edit 1 --lyrics "first line|second line|third line"

# Edit the featured word, definition, or part of speech
rapwords edit 1 --word "convalescent" --definition "recovering from illness" --pos noun

# Add or remove featured words
rapwords edit 1 --add-word "essence:noun:the core nature of something"
rapwords edit 1 --remove-word "essence"

# Add a brand new post (interactive prompts)
rapwords add

# Flag a post as unsuitable (e.g. no real music video)
rapwords flag 42 "audio only"
rapwords unflag 42
```

## Fonts

Subtitles use **Montserrat Bold**. Install it if not already available:

```bash
# Fedora
sudo dnf install julietaula-montserrat-fonts

# Ubuntu/Debian
sudo apt install fonts-montserrat
```

## Data

- `data/posts.json` — scraped blog posts (committed)
- `data/videos/` — downloaded YouTube clips (gitignored)
- `data/output/` — final Instagram-ready videos (gitignored)
