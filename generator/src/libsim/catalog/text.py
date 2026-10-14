"""Script/language checks and title cleanup.

Patterns are plain regex strings that work both in Python `re` and in Polars (Rust regex),
so the same rules drive unit tests and the vectorised catalogue build.
"""

import re

CYRILLIC_CHAR = "[Ѐ-ӿ]"
LATIN_CHAR = "[A-Za-z]"
# Letters used in Russian but never in Ukrainian: any of them disqualifies a string.
RUSSIAN_ONLY_CHAR = "[ЁёЪъЫыЭэ]"
UKRAINIAN_ONLY_CHAR = "[ҐґЄєІіЇї]"

# Things that are not books a reader borrows: proceedings, theses, bulletins, bills...
NON_BOOK = (
    r"(?i)\b(proceedings|conference|symposium|congress|dissertation|thesis|abstracts?|bulletin"
    r"|yearbook|catalog(ue)?|report of|annual report|bill \(|hearings?|transactions)\b"
    r"|конференц|симпозіум|з'їзд|матеріали|тези |збірник наукових|наукові праці|науковий вісник"
    r"|вісник|автореферат|дисертац|методичні (рекомендації|вказівки)|навчальн(ий|а) посібник"
)

# Language-learning material that contains Russian (e.g. Russian-Ukrainian dictionaries).
RUSSIAN_LANGUAGE_MATERIAL = (
    r"(?i)((словник|розмовник|dictionary|phrasebook).*(російськ|russian))"
    r"|((російськ|russian).*(словник|розмовник|dictionary|phrasebook))"
)
# School textbooks are not what library readers borrow.
SCHOOL_TEXTBOOK = r"(?i)підруч|для \d+[-–]?(го)?\s*кл\b|\btextbook\b"

_cyrillic = re.compile(CYRILLIC_CHAR)
_latin = re.compile(LATIN_CHAR)
_russian = re.compile(RUSSIAN_ONLY_CHAR)
_non_book = re.compile(NON_BOOK)
_by_statement = re.compile(r"\s+/\s+.*$")
_spaces = re.compile(r"\s+")


def has_russian_letters(text: str) -> bool:
    return bool(_russian.search(text))


def is_cyrillic_title(text: str) -> bool:
    """Mostly Cyrillic and free of Russian-only letters."""
    cyr, lat = len(_cyrillic.findall(text)), len(_latin.findall(text))
    return cyr > 0 and cyr >= 2 * lat and not has_russian_letters(text)


def is_latin_title(text: str) -> bool:
    return bool(_latin.search(text)) and not _cyrillic.search(text)


def is_non_book(title: str) -> bool:
    return bool(_non_book.search(title))


def clean_title(title: str) -> str:
    """Drop the trailing `/ by-statement`, collapse whitespace, trim punctuation."""
    title = _by_statement.sub("", title)
    title = _spaces.sub(" ", title).strip()
    return title.strip(" :;,./")


# Catalogue records often type Latin i/ï inside Ukrainian words ("Теорiя"). Replace them only
# when they touch a Cyrillic letter, so Latin words like "IT" stay intact. Applied twice to
# cover runs like "iї". (pattern, replacement) pairs work in `re` and in Polars.
LOOKALIKE_FIXES: list[tuple[str, str]] = [
    (rf"({CYRILLIC_CHAR})i", "${1}і"),
    (rf"i({CYRILLIC_CHAR})", "і${1}"),
    (rf"({CYRILLIC_CHAR})ï", "${1}ї"),
    (rf"ï({CYRILLIC_CHAR})", "ї${1}"),
    (rf"I({CYRILLIC_CHAR})", "І${1}"),
]


def fix_ukrainian_lookalikes(text: str) -> str:
    for _ in range(2):
        for pattern, replacement in LOOKALIKE_FIXES:
            text = re.sub(pattern, replacement.replace("${1}", r"\1"), text)
    return text


def fix_all_caps(title: str, language: str) -> str:
    """'THE MAMBA MENTALITY' → 'The Mamba Mentality'; Ukrainian uses sentence case."""
    letters = [c for c in title if c.isalpha()]
    if len(letters) < 4 or not all(c.isupper() for c in letters):
        return title
    if language == "uk":
        return title[:1] + title[1:].lower()
    return " ".join(word.capitalize() for word in title.split(" "))


# --- ALA-LC romanization of Ukrainian → Cyrillic (Library of Congress catalogue records) ---

LC_MARKS = re.compile("[\u0361\ufe20\ufe21ʹʺĭï]")
_LC_HALF_LIGATURE = re.compile("(\\w)\ufe20(\\w)\ufe21")
_LC_TABLE = [  # longest first; "͡" (U+0361) joins two letters into one Cyrillic letter
    ("shch", "щ"),
    ("z\u0361h", "ж"),
    ("t\u0361s", "ц"),
    ("i\u0361a", "я"),
    ("i\u0361u", "ю"),
    # Catalogers often drop ligatures; plain zh/ts then almost always mean ж/ц (Zhadan → Жадан).
    ("i\u0361e", "є"),
    ("kh", "х"),
    ("ch", "ч"),
    ("sh", "ш"),
    ("zh", "ж"),
    ("ts", "ц"),
    ("ia", "я"),
    ("iu", "ю"),
    ("ie", "є"),
    ("ĭ", "й"),
    ("ï", "ї"),
    ("ʹ", "ь"),
    ("ʺ", "'"),
    ("a", "а"),
    ("b", "б"),
    ("v", "в"),
    ("h", "г"),
    ("g", "ґ"),
    ("d", "д"),
    ("e", "е"),
    ("y", "и"),
    ("i", "і"),
    ("k", "к"),
    ("l", "л"),
    ("m", "м"),
    ("n", "н"),
    ("o", "о"),
    ("p", "п"),
    ("r", "р"),
    ("s", "с"),
    ("t", "т"),
    ("u", "у"),
    ("f", "ф"),
    ("z", "з"),
]


def lc_to_ukrainian(name: str) -> str:
    """Reverse ALA-LC romanization, but only for names that carry LC marks.

    Plain Latin names ("Norman Davies") are returned unchanged: without LC marks there is no
    evidence the name was romanized from Ukrainian.
    """
    name = _LC_HALF_LIGATURE.sub("\\1\u0361\\2", name)
    if not LC_MARKS.search(name):
        return name
    return re.sub(r"[^\W\d_][\w\u0361ʹʺ]*", _transliterate_word, name)


def _transliterate_word(match: re.Match[str]) -> str:
    word = match.group(0)
    lower, out, i = word.lower(), [], 0
    while i < len(lower):
        for latin, cyrillic in _LC_TABLE:
            if lower.startswith(latin, i):
                out.append(cyrillic)
                i += len(latin)
                break
        else:
            out.append(lower[i])
            i += 1
    result = "".join(out)
    return result[:1].upper() + result[1:] if word[:1].isupper() else result
