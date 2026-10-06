"""Normalisation des textes et détection du mot secret (module pur, bibliothèque standard)."""

import re
import unicodedata

# Articles initiaux retirés (FR-035)
_ARTICLES = ("les", "le", "la", "une", "un", "des")
_ROOT_PREFIX = 5  # longueur du préfixe commun qui trahit une racine évidente


def normalize(text: str) -> str:
    """Minuscules, accents supprimés, séparateurs unifiés, article initial retiré."""
    t = text.casefold().replace("œ", "oe").replace("æ", "ae").replace("’", "'")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9']+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    stripped = _strip_article(t)
    return stripped if stripped else t


def _strip_article(t: str) -> str:
    if t.startswith("l'"):
        return t[2:].strip()
    for art in _ARTICLES:
        if t.startswith(art + " "):
            return t[len(art) + 1 :].strip()
    return t


def _common_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        n += 1
    return n


def contains_secret_or_root(text: str, word: str) -> bool:
    """Vrai si le texte contient le mot (ou l'expression) ou une racine évidente de ce mot."""
    text_n = normalize(text)
    word_n = normalize(word)
    if not word_n:
        return False
    if f" {word_n} " in f" {text_n} ":
        return True
    for t in text_n.split():
        for w in word_n.split():
            if len(t) >= _ROOT_PREFIX and len(w) >= _ROOT_PREFIX:
                if _common_prefix(t, w) >= _ROOT_PREFIX:
                    return True
    return False
