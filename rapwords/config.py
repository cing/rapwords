import re
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
POSTS_FILE = DATA_DIR / "posts.json"
VIDEOS_DIR = DATA_DIR / "videos"
OUTPUT_DIR = DATA_DIR / "output"

TUMBLR_BASE_URL = "https://rapwords.tumblr.com"
TUMBLR_TOTAL_PAGES = 14

# Instagram Reel specs
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
DEFAULT_CLIP_DURATION = 20  # seconds

# Watermark
ASSETS_DIR = Path(__file__).parent / "assets"
WATERMARK_WHITE = ASSETS_DIR / "rapwords_white_dropshadow.png"
WATERMARK_BLACK = ASSETS_DIR / "rapwords_black_dropshadow.png"
WATERMARK_OPACITY = 0.6  # 0.0–1.0
WATERMARK_PADDING = 40  # pixels from edge

# Profanity filter for on-screen text and captions
_CENSORED = {
    "fuck": "f***",
    "fucked": "f*****",
    "fucker": "f*****",
    "fuckers": "f******",
    "fuckin": "f*****",
    "fucking": "f******",
    "fucks": "f****",
    "nigga": "n****",
    "niggas": "n*****",
}
_CENSOR_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in sorted(_CENSORED, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def censor_text(text: str) -> str:
    """Replace profanity with censored forms, preserving original case of the first letter."""
    def _replace(m: re.Match) -> str:
        matched = m.group()
        replacement = _CENSORED[matched.lower()]
        if matched[0].isupper():
            return replacement[0].upper() + replacement[1:]
        return replacement
    return _CENSOR_RE.sub(_replace, text)
