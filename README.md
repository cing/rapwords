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

# List all posts
rapwords list

# Show a specific post
rapwords show 1

# Download a YouTube video for a post
rapwords download 1

# Process a post into an Instagram-ready video
rapwords process 1 --start-time 01:23 --duration 20
```

## Data

- `data/posts.json` — scraped blog posts (committed)
- `data/videos/` — downloaded YouTube clips (gitignored)
- `data/output/` — final Instagram-ready videos (gitignored)
