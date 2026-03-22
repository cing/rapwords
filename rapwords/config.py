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
