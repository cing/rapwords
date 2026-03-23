from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class PartOfSpeech(str, Enum):
    NOUN = "noun"
    VERB = "verb"
    ADJECTIVE = "adjective"
    ADVERB = "adverb"
    OTHER = "other"


class FeaturedWord(BaseModel):
    word: str
    syllables: str | None = None
    part_of_speech: PartOfSpeech = PartOfSpeech.OTHER
    definition: str = ""
    wiktionary_url: str | None = None


class RapWordsPost(BaseModel):
    id: int
    source: str = "tumblr_scrape"
    words: list[FeaturedWord] = []
    lyrics_lines: list[str] = []
    artist: str = ""
    song_title: str = ""
    youtube_url: str | None = None
    youtube_video_id: str | None = None
    release_year: int | None = None
    tumblr_date: str | None = None

    # Flagging
    flag: str | None = None  # None = usable, otherwise reason (e.g. "no music video", "unavailable")

    # Processing state
    start_time: float | None = None  # seconds into the video
    duration: float | None = None  # clip duration in seconds
    video_downloaded: bool = False
    video_path: str | None = None
    output_path: str | None = None
    status: str = "scraped"  # scraped -> video_downloaded -> processed
