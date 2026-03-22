"""RapWords CLI — prepare Instagram Reel content from hip-hop vocabulary."""

from __future__ import annotations

import re

import click
from rich.console import Console
from rich.table import Table

from rapwords.content.store import PostStore
from rapwords.models import FeaturedWord, PartOfSpeech, RapWordsPost

console = Console()


@click.group()
def main():
    """RapWords — hip-hop vocabulary for Instagram Reels."""
    pass


@main.command()
def scrape():
    """Scrape posts from rapwords.tumblr.com."""
    from rapwords.scraper.tumblr import scrape_all

    store = PostStore()

    with console.status("[bold green]Scraping rapwords.tumblr.com...") as status:
        def progress(page, total):
            status.update(f"[bold green]Scraping page {page}/{total}...")

        posts = scrape_all(callback=progress)

    store.set_posts(posts)
    store.save()
    console.print(f"[green]Scraped {len(posts)} posts → data/posts.json[/green]")


@main.command("list")
@click.option("--status", "filter_status", default=None, help="Filter by status")
def list_posts(filter_status):
    """List all posts."""
    store = PostStore()
    posts = store.get_by_status(filter_status) if filter_status else store.get_all()

    if not posts:
        console.print("[yellow]No posts found. Run 'rapwords scrape' first.[/yellow]")
        return

    table = Table(title=f"RapWords Posts ({len(posts)} total)")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Word(s)", style="bold")
    table.add_column("Artist", style="green")
    table.add_column("Song", style="blue")
    table.add_column("Status", style="yellow")
    table.add_column("YT", justify="center")

    for post in posts:
        words = ", ".join(w.word for w in post.words)
        yt = "[green]✓[/green]" if post.youtube_video_id else "[red]✗[/red]"
        table.add_row(
            str(post.id),
            words,
            post.artist,
            post.song_title,
            post.status,
            yt,
        )

    console.print(table)


@main.command()
@click.argument("post_id", type=int)
def show(post_id):
    """Show details of a single post."""
    store = PostStore()
    post = store.get_by_id(post_id)

    if not post:
        console.print(f"[red]Post {post_id} not found.[/red]")
        return

    console.print()
    for word in post.words:
        console.print(f"[bold cyan]{word.syllables or word.word}[/bold cyan]")
        console.print(f"  {word.part_of_speech.value} — {word.definition}")
        if word.wiktionary_url:
            console.print(f"  {word.wiktionary_url}")
    console.print()

    for line in post.lyrics_lines:
        # Highlight featured words in the lyrics
        display_line = line
        for word in post.words:
            pattern = re.compile(re.escape(word.word), re.IGNORECASE)
            display_line = pattern.sub(f"[bold yellow]{word.word.upper()}[/bold yellow]", display_line)
        console.print(f"  {display_line}")
    console.print()

    console.print(f"  [green]— {post.artist}[/green] on [blue]\"{post.song_title}\"[/blue]")
    if post.youtube_url:
        console.print(f"  {post.youtube_url}")
    console.print(f"  Status: [yellow]{post.status}[/yellow]")
    if post.tumblr_date:
        console.print(f"  Posted: {post.tumblr_date}")
    console.print()


@main.command()
@click.argument("post_id", type=int)
def download(post_id):
    """Download YouTube video for a post."""
    from rapwords.video.downloader import download_video

    store = PostStore()
    post = store.get_by_id(post_id)

    if not post:
        console.print(f"[red]Post {post_id} not found.[/red]")
        return

    if not post.youtube_video_id:
        console.print(f"[red]Post {post_id} has no YouTube link.[/red]")
        return

    words = ", ".join(w.word for w in post.words)
    console.print(f"Downloading video for [bold]{words}[/bold] — {post.artist} \"{post.song_title}\"")

    result = download_video(post)
    if result:
        post.video_downloaded = True
        post.video_path = result
        post.status = "video_downloaded"
        store.update(post)
        store.save()
        console.print(f"[green]Downloaded → {result}[/green]")
    else:
        console.print("[red]Download failed.[/red]")


@main.command("download-all")
def download_all():
    """Download YouTube videos for all posts."""
    from rapwords.video.downloader import download_video

    store = PostStore()
    posts = [p for p in store.get_all() if p.youtube_video_id and not p.video_downloaded]

    if not posts:
        console.print("[yellow]No posts to download.[/yellow]")
        return

    success = 0
    failed = 0
    for i, post in enumerate(posts, 1):
        words = ", ".join(w.word for w in post.words)
        console.print(f"[{i}/{len(posts)}] {words} — {post.artist}... ", end="")

        result = download_video(post)
        if result:
            post.video_downloaded = True
            post.video_path = result
            post.status = "video_downloaded"
            store.update(post)
            success += 1
            console.print("[green]OK[/green]")
        else:
            failed += 1
            console.print("[red]FAILED[/red]")

    store.save()
    console.print(f"\n[green]{success} downloaded[/green], [red]{failed} failed[/red]")


@main.command()
@click.argument("post_id", type=int)
@click.option("--start-time", type=str, default=None, help="Start time in video (MM:SS or HH:MM:SS)")
@click.option("--duration", type=float, default=None, help="Clip duration in seconds")
def process(post_id, start_time, duration):
    """Process a post into an Instagram-ready video with karaoke subtitles."""
    from rapwords.video.downloader import download_video
    from rapwords.video.processor import process_post

    store = PostStore()
    post = store.get_by_id(post_id)

    if not post:
        console.print(f"[red]Post {post_id} not found.[/red]")
        return

    # Show post details
    console.print()
    for word in post.words:
        console.print(f"[bold cyan]{word.syllables or word.word}[/bold cyan] — {word.part_of_speech.value} — {word.definition}")
    console.print()
    for line in post.lyrics_lines:
        console.print(f"  {line}")
    console.print(f"\n  [green]{post.artist}[/green] — \"{post.song_title}\"")
    if post.youtube_url:
        console.print(f"  {post.youtube_url}")
    console.print()

    # Ensure video is downloaded
    if not post.video_downloaded or not post.video_path:
        if not post.youtube_video_id:
            console.print("[red]No YouTube link for this post.[/red]")
            return
        console.print("Downloading video...")
        result = download_video(post)
        if not result:
            console.print("[red]Download failed.[/red]")
            return
        post.video_downloaded = True
        post.video_path = result
        post.status = "video_downloaded"

    # Get start time
    if start_time is None:
        start_time = click.prompt("Start time (MM:SS or HH:MM:SS)")

    start_seconds = _parse_time(start_time)
    if start_seconds is None:
        console.print("[red]Invalid time format.[/red]")
        return

    if duration is None:
        from rapwords.config import DEFAULT_CLIP_DURATION
        duration = click.prompt("Duration (seconds)", default=DEFAULT_CLIP_DURATION, type=float)

    post.start_time = start_seconds
    post.duration = duration

    console.print(f"\nProcessing: {start_time} + {duration}s ...")
    output = process_post(post)
    if output:
        post.output_path = output
        post.status = "processed"
        store.update(post)
        store.save()
        console.print(f"[green]Output → {output}[/green]")
    else:
        console.print("[red]Processing failed.[/red]")


def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from a URL."""
    from urllib.parse import parse_qs, urlparse
    parsed = urlparse(url)
    if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]
        if parsed.path and len(parsed.path) > 1:
            return parsed.path.lstrip("/")
    return None


@main.command()
@click.argument("post_id", type=int)
@click.option("--youtube-url", type=str, default=None, help="New YouTube URL")
@click.option("--artist", type=str, default=None, help="Artist name")
@click.option("--song", type=str, default=None, help="Song title")
@click.option("--lyrics", type=str, default=None, help="Lyrics lines (use | to separate lines)")
@click.option("--word", type=str, default=None, help="Edit/replace first featured word")
@click.option("--definition", type=str, default=None, help="Edit definition of first featured word")
@click.option("--pos", type=click.Choice(["noun", "verb", "adjective", "adverb", "other"]), default=None, help="Part of speech of first featured word")
@click.option("--add-word", type=str, default=None, help="Add a new featured word (word:pos:definition)")
@click.option("--remove-word", type=str, default=None, help="Remove a featured word by name")
def edit(post_id, youtube_url, artist, song, lyrics, word, definition, pos, add_word, remove_word):
    """Edit fields of an existing post.

    Examples:

      rapwords edit 1 --youtube-url "https://youtube.com/watch?v=..."

      rapwords edit 1 --artist "2Pac" --song "I Ain't Mad at Cha"

      rapwords edit 1 --lyrics "line one|line two|line three"

      rapwords edit 1 --word "convalescent" --definition "recovering from illness"

      rapwords edit 1 --add-word "essence:noun:the core nature of something"

      rapwords edit 1 --remove-word "convalescent"
    """
    store = PostStore()
    post = store.get_by_id(post_id)

    if not post:
        console.print(f"[red]Post {post_id} not found.[/red]")
        return

    changes = []

    if youtube_url is not None:
        old_url = post.youtube_url
        post.youtube_url = youtube_url
        post.youtube_video_id = _extract_video_id(youtube_url)
        # Reset download state since the video source changed
        post.video_downloaded = False
        post.video_path = None
        post.output_path = None
        if post.status in ("video_downloaded", "processed"):
            post.status = "scraped"
        changes.append(f"youtube_url: {old_url} → {youtube_url}")
        if post.youtube_video_id:
            changes.append(f"youtube_video_id: {post.youtube_video_id}")
        else:
            console.print("[yellow]Warning: could not extract video ID from URL[/yellow]")

    if artist is not None:
        changes.append(f"artist: {post.artist} → {artist}")
        post.artist = artist

    if song is not None:
        changes.append(f"song_title: {post.song_title} → {song}")
        post.song_title = song

    if lyrics is not None:
        post.lyrics_lines = [line.strip() for line in lyrics.split("|") if line.strip()]
        changes.append(f"lyrics: {len(post.lyrics_lines)} lines")

    if word is not None and post.words:
        old_word = post.words[0].word
        post.words[0].word = word
        changes.append(f"word: {old_word} → {word}")

    if definition is not None and post.words:
        post.words[0].definition = definition
        changes.append(f"definition updated for {post.words[0].word}")

    if pos is not None and post.words:
        post.words[0].part_of_speech = PartOfSpeech(pos)
        changes.append(f"pos: {pos} for {post.words[0].word}")

    if add_word is not None:
        parts = add_word.split(":", 2)
        new_word = FeaturedWord(
            word=parts[0],
            part_of_speech=PartOfSpeech(parts[1]) if len(parts) > 1 else PartOfSpeech.OTHER,
            definition=parts[2] if len(parts) > 2 else "",
        )
        post.words.append(new_word)
        changes.append(f"added word: {new_word.word}")

    if remove_word is not None:
        before = len(post.words)
        post.words = [w for w in post.words if w.word.lower() != remove_word.lower()]
        if len(post.words) < before:
            changes.append(f"removed word: {remove_word}")
        else:
            console.print(f"[yellow]Word '{remove_word}' not found in post.[/yellow]")

    if not changes:
        console.print("[yellow]No changes specified. Use --help to see options.[/yellow]")
        return

    store.update(post)
    store.save()

    console.print("[green]Updated post {id}:[/green]".format(id=post_id))
    for c in changes:
        console.print(f"  {c}")


@main.command()
@click.option("--artist", prompt="Artist", help="Artist name")
@click.option("--song", prompt="Song title", help="Song title")
@click.option("--youtube-url", prompt="YouTube URL", default="", help="YouTube URL")
@click.option("--lyrics", prompt="Lyrics (separate lines with |)", help="Lyrics lines separated by |")
@click.option("--word", prompt="Featured word", help="The vocabulary word")
@click.option("--pos", prompt="Part of speech", type=click.Choice(["noun", "verb", "adjective", "adverb", "other"]), help="Part of speech")
@click.option("--definition", prompt="Definition", help="Word definition")
def add(artist, song, youtube_url, lyrics, word, pos, definition):
    """Add a new post interactively."""
    store = PostStore()

    post = RapWordsPost(
        id=store.next_id(),
        source="manual",
        artist=artist,
        song_title=song,
        youtube_url=youtube_url or None,
        youtube_video_id=_extract_video_id(youtube_url) if youtube_url else None,
        lyrics_lines=[line.strip() for line in lyrics.split("|") if line.strip()],
        words=[
            FeaturedWord(
                word=word,
                part_of_speech=PartOfSpeech(pos),
                definition=definition,
            )
        ],
    )

    # Prompt for additional words
    while click.confirm("Add another featured word?", default=False):
        w = click.prompt("Word")
        p = click.prompt("Part of speech", type=click.Choice(["noun", "verb", "adjective", "adverb", "other"]))
        d = click.prompt("Definition")
        post.words.append(FeaturedWord(word=w, part_of_speech=PartOfSpeech(p), definition=d))

    store.add(post)
    store.save()

    console.print(f"\n[green]Created post {post.id}:[/green]")
    for w in post.words:
        console.print(f"  [bold cyan]{w.word}[/bold cyan] — {w.part_of_speech.value} — {w.definition}")
    console.print(f"  {post.artist} — \"{post.song_title}\"")
    if post.youtube_video_id:
        console.print(f"  YouTube: {post.youtube_url}")


def _parse_time(time_str: str) -> float | None:
    """Parse MM:SS or HH:MM:SS to seconds."""
    parts = time_str.strip().split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else:
            return float(time_str)
    except ValueError:
        return None


if __name__ == "__main__":
    main()
