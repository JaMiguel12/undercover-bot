"""Base de mots : chargement, validation et tirage (FR-056 à FR-059)."""

import json
import random
from dataclasses import dataclass
from pathlib import Path

from game.models import WordTrio
from game.normalize import normalize


class WordsError(Exception):
    """Base de mots invalide : le message nomme l'identifiant fautif."""


def load_words(path: str | Path) -> list[WordTrio]:
    """Charge et valide la base ; id unique, exactement 3 mots distincts par trio."""
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WordsError(f"Impossible de lire la base de mots {p} : {exc}") from exc
    if not isinstance(data, list):
        raise WordsError(f"La base de mots {p} doit être un tableau JSON")
    trios: list[WordTrio] = []
    seen: set[int] = set()
    for index, obj in enumerate(data):
        if not isinstance(obj, dict) or not {"id", "categorie", "mots"} <= obj.keys():
            raise WordsError(f"Entrée {index} invalide : champs id, categorie et mots requis")
        tid = obj["id"]
        if not isinstance(tid, int) or isinstance(tid, bool):
            raise WordsError(f"Entrée {index} invalide : id entier requis")
        if tid in seen:
            raise WordsError(f"Identifiant en double : {tid}")
        seen.add(tid)
        words = obj["mots"]
        if (
            not isinstance(words, list)
            or len(words) != 3
            or not all(isinstance(w, str) and w.strip() for w in words)
        ):
            raise WordsError(f"Trio {tid} : exactement 3 mots non vides requis")
        if len({normalize(w) for w in words}) != 3:
            raise WordsError(f"Trio {tid} : les 3 mots doivent être distincts")
        category = obj["categorie"]
        if not isinstance(category, str) or not category.strip():
            raise WordsError(f"Trio {tid} : catégorie non vide requise")
        trios.append(WordTrio(tid, category, (words[0], words[1], words[2])))
    return trios


@dataclass(frozen=True)
class Draw:
    """Résultat d'un tirage : le trio et deux de ses mots, tirés au hasard (civils, undercover)."""

    trio: WordTrio
    civilian: str
    undercover: str
    cycle_restarted: bool


def draw(trios: list[WordTrio], played_ids: set[int], rng: random.Random) -> Draw:
    """Tire un trio non joué ; repart de zéro quand tous ont été joués (FR-058)."""
    available = [t for t in trios if t.id not in played_ids]
    restarted = False
    if not available:
        available = list(trios)
        restarted = True
    trio = rng.choice(available)
    words = list(trio.words)
    rng.shuffle(words)
    return Draw(trio, words[0], words[1], restarted)
