import json
import random

import pytest

from game.words import WordsError, load_words


def write(tmp_path, data):
    p = tmp_path / "words.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def trio(i, words=("a1", "b2", "c3"), cat="Cat"):
    return {"id": i, "categorie": cat, "mots": list(words)}


def test_valid_database(tmp_path):
    trios = load_words(write(tmp_path, [trio(1), trio(2, ("x", "y", "z"))]))
    assert [t.id for t in trios] == [1, 2]
    assert trios[0].words == ("a1", "b2", "c3")
    assert trios[0].category == "Cat"


def test_not_an_array(tmp_path):
    with pytest.raises(WordsError):
        load_words(write(tmp_path, {"id": 1}))


def test_unreadable_file(tmp_path):
    with pytest.raises(WordsError):
        load_words(tmp_path / "absent.json")


@pytest.mark.parametrize("missing", ["id", "categorie", "mots"])
def test_missing_field(tmp_path, missing):
    obj = trio(1)
    del obj[missing]
    with pytest.raises(WordsError):
        load_words(write(tmp_path, [obj]))


def test_duplicate_id_names_the_id(tmp_path):
    with pytest.raises(WordsError, match="7"):
        load_words(write(tmp_path, [trio(7), trio(7, ("x", "y", "z"))]))


@pytest.mark.parametrize("words", [("a", "b"), ("a", "b", "c", "d"), ("a", "b", "")])
def test_wrong_words(tmp_path, words):
    with pytest.raises(WordsError, match="3"):
        load_words(write(tmp_path, [trio(3, words)]))


def test_identical_after_normalization(tmp_path):
    with pytest.raises(WordsError, match="5"):
        load_words(write(tmp_path, [trio(5, ("Thé", "the", "café"))]))


def test_load_returns_independent_objects(tmp_path):
    a = load_words(write(tmp_path, [trio(1)]))
    b = load_words(write(tmp_path, [trio(1)]))
    assert a == b
    assert isinstance(a[0].words, tuple)
    assert random.Random(0)  # sanity
