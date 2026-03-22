"""Fetch word definitions from the Free Dictionary API with POS disambiguation."""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests


@dataclass
class WordDefinition:
    word: str
    part_of_speech: str
    definition: str
    wiktionary_url: str


# Map NLTK universal POS tags to dictionary POS labels
_POS_MAP = {
    "noun": "noun",
    "verb": "verb",
    "adj": "adjective",
    "adv": "adverb",
    "adp": "other",
    "det": "other",
    "pron": "other",
}

_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"


def get_definition(word: str, context_sentence: str | None = None) -> WordDefinition | None:
    """Fetch a definition for a word from the Free Dictionary API.

    If context_sentence is provided, uses NLTK POS tagging to pick the
    definition matching the word's grammatical role.
    """
    try:
        resp = requests.get(_API_URL.format(word=word.lower()), timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception:
        return None

    if not isinstance(data, list) or not data:
        return None

    url = f"https://en.wiktionary.org/wiki/{word.lower()}"

    # Collect all definitions
    all_defs: list[tuple[str, str]] = []
    for entry in data:
        for meaning in entry.get("meanings", []):
            pos = meaning.get("partOfSpeech", "").lower()
            definitions = meaning.get("definitions", [])
            if definitions and pos:
                # Strip HTML tags from definition text
                defn = re.sub(r"<[^>]+>", "", definitions[0].get("definition", ""))
                if defn:
                    all_defs.append((pos, defn))

    if not all_defs:
        return None

    # If we have a context sentence, try to match POS
    if context_sentence:
        target_pos = _get_word_pos(word, context_sentence)
        if target_pos:
            for pos, defn in all_defs:
                if pos == target_pos:
                    return WordDefinition(word=word, part_of_speech=pos, definition=defn, wiktionary_url=url)

    # Fallback: first definition
    pos, defn = all_defs[0]
    return WordDefinition(word=word, part_of_speech=pos, definition=defn, wiktionary_url=url)


def _get_word_pos(word: str, sentence: str) -> str | None:
    """Use NLTK to determine the POS of a word in a sentence."""
    try:
        import nltk
        tokens = nltk.word_tokenize(sentence)
        tagged = nltk.pos_tag(tokens, tagset="universal")
        for token, pos in tagged:
            if token.lower() == word.lower():
                return _POS_MAP.get(pos.lower(), pos.lower())
    except Exception:
        pass
    return None
