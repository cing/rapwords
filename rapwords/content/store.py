from __future__ import annotations

import json
from pathlib import Path

from rapwords.config import POSTS_FILE
from rapwords.models import RapWordsPost


class PostStore:
    def __init__(self, path: Path = POSTS_FILE):
        self.path = path
        self._posts: list[RapWordsPost] = []
        if self.path.exists():
            self._load()

    def _load(self):
        data = json.loads(self.path.read_text())
        self._posts = [RapWordsPost(**p) for p in data]

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [p.model_dump() for p in self._posts]
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def get_all(self) -> list[RapWordsPost]:
        return list(self._posts)

    def get_by_id(self, post_id: int) -> RapWordsPost | None:
        for p in self._posts:
            if p.id == post_id:
                return p
        return None

    def get_by_status(self, status: str) -> list[RapWordsPost]:
        return [p for p in self._posts if p.status == status]

    def add(self, post: RapWordsPost):
        self._posts.append(post)

    def set_posts(self, posts: list[RapWordsPost]):
        self._posts = posts

    def update(self, post: RapWordsPost):
        for i, p in enumerate(self._posts):
            if p.id == post.id:
                self._posts[i] = post
                return
        raise ValueError(f"Post {post.id} not found")

    def next_id(self) -> int:
        if not self._posts:
            return 1
        return max(p.id for p in self._posts) + 1

    def count(self) -> int:
        return len(self._posts)
