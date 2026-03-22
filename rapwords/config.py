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
