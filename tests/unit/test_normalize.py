import pytest

from game.normalize import contains_secret_or_root, normalize


@pytest.mark.parametrize(
    "a,b",
    [
        ("L'ananas", "ananas"),
        ("un Ananas", "ananas"),
        ("Une ANANAS", "ananas"),
        ("les bananes", "bananes"),
        ("Coca-Cola", "coca cola"),
        ("café", "cafe"),
        ("  poulet   DG ", "poulet dg"),
        ("œuf dur", "oeuf dur"),
        ("l’ananas", "ananas"),
        ("des pâtes", "pates"),
    ],
)
def test_normalize_equivalences(a, b):
    assert normalize(a) == normalize(b)


def test_normalize_keeps_word_when_only_an_article():
    assert normalize("le") == "le"


def test_normalize_unifies_separators():
    assert normalize("ping-pong") == normalize("ping pong") == "ping pong"


@pytest.mark.parametrize(
    "text,word,expected",
    [
        ("du thé noir", "thé", True),
        ("c'est un THE", "thé", True),
        ("le thème", "thé", False),
        ("cuisinière", "cuisinier", True),
        ("très chocolat", "chocolat chaud", True),
        ("rien à voir", "chocolat chaud", False),
        ("riz", "riz sauté", False),
        ("on mange le poulet DG", "poulet DG", True),
        ("bonne cuisine", "cuisinier", True),
        ("bonne recette", "cuisinier", False),
    ],
)
def test_contains_secret_or_root(text, word, expected):
    assert contains_secret_or_root(text, word) is expected
