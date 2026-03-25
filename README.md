# RapWords

Prepare Instagram Reel content from hip-hop vocabulary — short video clips from YouTube music videos with karaoke-style subtitle overlays highlighting featured vocabulary words.

Follow on Instagram: [@rapwordstv](https://www.instagram.com/rapwordstv/)

Originally a [Tumblr blog](https://rapwords.tumblr.com/) and [PyCon Canada 2016 talk](archive/RapWordsTalk.ipynb).

## Prerequisites

- Python 3.10+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for video downloads
- [deno](https://deno.land/) JavaScript runtime (required by yt-dlp for YouTube signature solving)
- [ffmpeg](https://ffmpeg.org/) built with libass for subtitle rendering
- `GENIUS_API_TOKEN` env var for discovering new content (free at https://genius.com/api-clients)

## Install

```bash
pip install -e .

# Install deno (needed by yt-dlp)
curl -fsSL https://deno.land/install.sh | sh
echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc
```

## Usage

```bash
# Scrape historical blog posts from rapwords.tumblr.com
rapwords scrape

# List all posts (hides posted and flagged by default)
rapwords list
rapwords list --usable        # unflagged only
rapwords list --flagged       # flagged only
rapwords list --posted        # posted only
rapwords list --all           # everything

# Show a specific post
rapwords show 1

# Find where lyrics appear in a YouTube video using auto-captions
rapwords find-time 1

# Download a YouTube video for a post
rapwords download 1
rapwords download 1 --cookies firefox   # for age-restricted videos

# Process a post into an Instagram-ready video
rapwords process 1 --start-time 01:23 --duration 20

# Generate an Instagram caption (also shown after processing)
rapwords caption 1

# Look up all definitions for a word
rapwords lookup bespoke
rapwords lookup bespoke --context "before he speak his suit bespoke"

# Track posting status
rapwords mark-posted 1
rapwords unmark-posted 1
```

### Process options

| Option | Default | Effect |
|---|---|---|
| `--crop/--no-crop` | on | Crop to fill 9:16 (off = pad with black bars) |
| `--crop-offset` | 0 | Shift crop horizontally in pixels (+right, -left) |
| `--theme` | yellow | Lyrics color theme: `yellow`, `pink`, or `ice` |
| `--watermark` | white | Logo watermark: `white`, `black`, or `none` |
| `--watermark-scale` | 0.7 | Watermark size multiplier |
| `--static/--no-static` | on | TV static outro with hard cut and white noise |
| `--align/--no-align` | on | Use whisperX for word-level karaoke timing |
| `--ass-file` | — | Use a manually edited `.ass` subtitle file |
| `--attribution/--no-attribution` | off | Show artist/song text overlay |
| `--cookies` | — | Browser to extract cookies from for age-restricted videos |

To fine-tune subtitle timings: process once to generate the `.ass` file in `data/output/`, edit it, then re-render with `--ass-file`.

### Audio alignment

Word-level karaoke timing uses [whisperX](https://github.com/m-bain/whisperX) forced alignment (CPU mode, base model). Falls back to YouTube auto-captions for line-level timing, then to syllable-weighted estimation if neither is available. Disable with `--no-align`.

## Discovering new content

Scan hip-hop lyrics from Genius for "big words" — rare vocabulary identified using the [Zipf frequency scale](https://pypi.org/project/wordfreq/) (multi-source word frequency aggregated from Wikipedia, Reddit, subtitles, and books) cross-referenced with the Scrabble dictionary.

```bash
# Scan a specific song
rapwords discover --artist "Kendrick Lamar" --song "HUMBLE."

# Scan an artist's top songs
rapwords discover --artist "Aesop Rock" --max-songs 10

# Find a specific word in an artist's lyrics
rapwords discover --artist "Talib Kweli" --word "ubiquitous"

# Auto-add all discovered words without prompting
rapwords discover --artist "MF DOOM" --auto

# Stricter filtering: only rarer, longer words
rapwords discover --artist "Aesop Rock" --max-zipf 3.0 --min-length 7
```

For each big word found, the pipeline:
1. Extracts the surrounding bars (grouped by rhyming end-words)
2. Fetches a definition and syllable breakdown from Wiktionary
3. Finds the official YouTube music video
4. Shows other songs containing the word (via Genius search)

Discovered posts are saved to `data/posts.json` and work with the full `download` → `find-time` → `process` workflow.

| Option | Default | Effect |
|---|---|---|
| `--max-zipf` | 3.5 | Max Zipf score — lower = rarer words only |
| `--min-length` | 5 | Minimum word length |
| `--max-songs` | 20 | Songs to scan when no `--song` given |
| `--word` | — | Find a specific word in the artist's lyrics |
| `--auto` | off | Skip interactive selection, add all |

**Zipf scale reference:** 7–8 ultra-common ("the"), 5–6 common ("people"), 3–4 uncommon ("ubiquitous"), 1–2 rare ("defenestrate").

## Editing posts

```bash
# Update the YouTube video for a post (resets download state)
rapwords edit 1 --youtube-url "https://youtube.com/watch?v=NEW_ID"

# Change artist or song title
rapwords edit 1 --artist "2Pac" --song "I Ain't Mad at Cha"

# Replace lyrics (use | to separate lines)
rapwords edit 1 --lyrics "first line|second line|third line"

# Edit the featured word, definition, part of speech, or syllable breaks
rapwords edit 1 --word "convalescent" --definition "recovering from illness" --pos noun
rapwords edit 1 --syllables "con·va·les·cent"

# Set release year
rapwords edit 1 --year 1996

# Add or remove featured words
rapwords edit 1 --add-word "essence:noun:the core nature of something"
rapwords edit 1 --remove-word "essence"

# Add a brand new post (interactive prompts)
rapwords add

# Flag a post as unsuitable (e.g. no real music video)
rapwords flag 42 "audio only"
rapwords unflag 42

# Backfill release years from Genius for all posts
rapwords backfill-years
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
- `data/output/` — final Instagram-ready videos and `.ass` subtitle files (gitignored)
