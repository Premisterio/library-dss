"""Pure catalogue rules: scripts, Russian-content filters, title/name cleanup, genres."""

import pytest

from libsim.catalog import genres, text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Гаррі Поттер і філософський камінь", True),
        ("Кайдашева сімʼя", True),
        ("Подъезд", False),  # ъ never occurs in Ukrainian
        ("Harry Potter", False),
    ],
)
def test_is_cyrillic_title(value: str, expected: bool) -> None:
    assert text.is_cyrillic_title(value) is expected


def test_letter_heuristic_is_only_a_second_line_of_defence() -> None:
    # Many Russian titles use no ё/ъ/ы/э. They are excluded by the primary rule (only editions
    # tagged as Ukrainian or English qualify), not by this heuristic.
    assert text.is_cyrillic_title("Мастер и Маргарита") is True


def test_russian_only_letters() -> None:
    assert text.has_russian_letters("Ёлка")
    assert text.has_russian_letters("объект")
    assert not text.has_russian_letters("Їжак і ґанок")


def test_russian_language_material_is_excluded() -> None:
    import re

    pattern = re.compile(text.RUSSIAN_LANGUAGE_MATERIAL)
    assert pattern.search("Російсько-український словник з інженерних технологій")
    assert pattern.search("Українсько-російсько-білоруський словник")
    assert pattern.search("Russian-English dictionary")
    # Ukrainian history about Russia is legitimate Ukrainian content.
    assert not pattern.search("Російсько-українська війна: хроніка")


def test_non_book_and_textbooks() -> None:
    import re

    assert text.is_non_book("Proceedings of the conference on libraries")
    assert text.is_non_book("Матеріали наукової конференції")
    assert not text.is_non_book("Тіні забутих предків")
    textbook = re.compile(text.SCHOOL_TEXTBOOK)
    assert textbook.search("Географія: підруч. для 11-го кл.")
    assert not textbook.search("Кобзар")


def test_clean_title() -> None:
    assert text.clean_title("Lirychnyĭ vinok / I︠A︡roslav Shporta") == "Lirychnyĭ vinok"
    assert text.clean_title("  Dune :  ") == "Dune"


def test_fix_lookalikes_only_inside_cyrillic_words() -> None:
    assert text.fix_ukrainian_lookalikes("Теорiя держави") == "Теорія держави"
    assert text.fix_ukrainian_lookalikes("IT-бізнес") == "IT-бізнес"


def test_fix_all_caps() -> None:
    assert text.fix_all_caps("THE MAMBA MENTALITY", "en") == "The Mamba Mentality"
    assert text.fix_all_caps("ЛИЦАРІ ЛЮБОВІ І НАДІЇ", "uk") == "Лицарі любові і надії"
    assert text.fix_all_caps("The Hobbit", "en") == "The Hobbit"


@pytest.mark.parametrize(
    ("romanized", "cyrillic"),
    [
        ("Andriĭ Kokoti͡ukha", "Андрій Кокотюха"),
        ("O. A. Dubaseni︠u︡k", "О. А. Дубасенюк"),
        ("Serhiĭ Zhadan", "Сергій Жадан"),
        ("Iaroslav Shporta", "Iaroslav Shporta"),  # no LC marks: left as is
        ("Norman Davies", "Norman Davies"),
    ],
)
def test_lc_romanization_to_ukrainian(romanized: str, cyrillic: str) -> None:
    assert text.lc_to_ukrainian(romanized) == cyrillic


@pytest.mark.parametrize(
    ("subjects", "genre"),
    [
        (["Drama", "Plays", "Juvenile drama", "murder of the King", "Fiction"], "poetry_drama"),
        (
            ["Fantasy fiction", "Magic", "Wizards", "Schools, fiction", "England, fiction"],
            "fantasy",
        ),
        (
            ["Dystopian fiction", "Fiction, dystopian", "fantasy fiction", "Fiction"],
            "science_fiction",
        ),
        (["Biography", "Memoir", "Horror tales--Authorship", "Authorship"], "biography"),
        (["Fiction, historical", "Fiction", "War, fiction"], "historical_fiction"),
        (["Political science", "Politics and government", "Philosophy"], "society_politics"),
        (["Large type books"], None),
    ],
)
def test_classify_votes(subjects: list[str], genre: str | None) -> None:
    assert genres.classify(subjects) == genre


def test_generic_fiction_votes_are_weak() -> None:
    # 5 generic votes weigh 5/3 < 2 specific votes.
    subjects = [f"Place {i}, fiction" for i in range(5)] + ["Horror stories", "Ghost stories"]
    assert genres.classify(subjects) == "horror"
    # ...but plenty of generic votes still beat a lone specific one.
    assert (
        genres.classify([f"Place {i}, fiction" for i in range(6)] + ["Horror stories"]) == "fiction"
    )


def test_classics_rules() -> None:
    assert genres.with_classics("fiction", 1925) == "classics"
    assert genres.with_classics("fiction", 1999) == "fiction"
    assert genres.with_classics("society_politics", 1532, ["Classic Literature"]) == "classics"
    # Christie stays a mystery even with a "classic" marker.
    assert (
        genres.with_classics("mystery_thriller", 1937, ["Classic Literature"]) == "mystery_thriller"
    )


def test_every_genre_has_a_ukrainian_label() -> None:
    assert set(genres.GENRE_ORDER) | {"classics"} == set(genres.GENRES)
