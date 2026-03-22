# RapWords

Prepare Instagram Reel content from hip-hop vocabulary — short video clips from YouTube music videos with karaoke-style subtitle overlays highlighting featured vocabulary words.

Originally a [Tumblr blog](https://rapwords.tumblr.com/) and [PyCon Canada 2016 talk](archive/RapWordsTalk.ipynb).

## Prerequisites

- Python 3.10+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for video downloads
- [ffmpeg](https://ffmpeg.org/) built with libass for subtitle rendering

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
```

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

## Data

- `data/posts.json` — scraped blog posts (committed)
- `data/videos/` — downloaded YouTube clips (gitignored)
- `data/output/` — final Instagram-ready videos (gitignored)
