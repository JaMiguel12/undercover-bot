from pathlib import Path

from game.words import load_words

WORDS_FILE = Path(__file__).resolve().parents[2] / "data" / "words.json"


def test_shipped_database_is_valid():
    trios = load_words(WORDS_FILE)
    assert len(trios) == 201
    assert len({t.category for t in trios}) == 15
    assert len({t.id for t in trios}) == 201
    assert all(len(set(t.words)) == 3 for t in trios)
