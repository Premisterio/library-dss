"""Controlled genre taxonomy and rules that map free-form subjects/tags onto it.

Open Library subjects and goodbooks-10k shelf tags are user-generated and noisy (a work
often has 50-150 subjects). Classification therefore *votes*: each subject casts one vote for
the first rule it matches (rules go from specific fiction genres to generic fiction to
non-fiction topics, so "Fantasy fiction" votes fantasy, not fiction). The genre with most votes
wins; ties go to the earlier rule. Macbeth's "Drama", "Plays", "Juvenile drama" thus outvote
a single "murder of the King".
"""

import re
from collections import Counter
from collections.abc import Iterable

# code -> Ukrainian label (shown in the UI via the API's meta/enums)
GENRES: dict[str, str] = {
    "fantasy": "Фентезі",
    "science_fiction": "Наукова фантастика",
    "mystery_thriller": "Детективи й трилери",
    "romance": "Любовні романи",
    "horror": "Жахи",
    "historical_fiction": "Історична проза",
    "children": "Дитяча література",
    "young_adult": "Підліткова література",
    "poetry_drama": "Поезія й драматургія",
    "classics": "Класика",
    "fiction": "Сучасна проза",
    "biography": "Біографії й мемуари",
    "history": "Історія",
    "philosophy_religion": "Філософія й релігія",
    "self_help": "Психологія й саморозвиток",
    "business": "Бізнес і економіка",
    "technology": "Технології",
    "science": "Наука",
    "society_politics": "Суспільство й політика",
    "arts": "Мистецтво",
    "education_reference": "Навчальна й довідкова",
}


def _rx(english: Iterable[str], ukrainian: Iterable[str] = ()) -> str:
    words = "|".join(english)
    stems = "|".join(ukrainian)
    return rf"(?i)\b({words})\b" + (f"|{stems}" if stems else "")


# (genre, regex) in priority order. `classics` is assigned later from the publication year.
RULES: list[tuple[str, str]] = [
    (
        "fantasy",
        _rx(
            [
                "fantasy",
                "magic",
                "wizards?",
                "witch\\w*",
                "dragons?",
                "elves",
                "sorcery",
                "fairies",
                "mytholog\\w*",
                "gods",
                "goddesses",
                "demigods",
                "imaginary",
            ],
            ["фентезі", "міфолог"],
        ),
    ),
    (
        "science_fiction",
        _rx(
            ["science fiction", "sci-fi", r"dystopi\w*", "time travel", "space opera", "cyberpunk"],
            ["фантастик"],
        ),
    ),
    (
        "mystery_thriller",
        _rx(
            [
                "detective",
                "detectives",
                "mystery",
                "mysteries",
                "thrillers?",
                "crime",
                "suspense",
                "murder",
                "spy stories",
            ],
            ["детектив", "трилер"],
        ),
    ),
    ("horror", _rx(["horror", "ghost stories", "vampires?", "zombies?", "supernatural"], ["жахи"])),
    ("romance", _rx(["romance", "love stories", "romantic fiction"], ["любовн"])),
    (
        "historical_fiction",
        _rx(
            ["historical fiction", "fiction, historical", "historical novels?"],
            ["історичний роман"],
        ),
    ),
    (
        "children",
        _rx(
            [
                "juvenile fiction",
                "juvenile literature",
                "children's stories",
                "children's books",
                "picture books",
                "fairy tales",
                "childrens",
            ],
            ["дитяч", "казки"],
        ),
    ),
    (
        "young_adult",
        _rx(["young adult", "young-adult", "teen", "teenagers?", "ya fiction"], ["підлітк"]),
    ),
    (
        "poetry_drama",
        _rx(["poetry", "poems", "poets", "drama", "plays", "verse"], ["поезі", "вірш", "драм"]),
    ),
    (
        "fiction",
        _rx(
            [
                "fiction",
                "novels?",
                "short stories",
                "literary fiction",
                "contemporary",
                "humor",
                "satire",
            ],
            ["роман", "повість", "повісті", "проза", "оповідан", "новел"],
        ),
    ),
    (
        "biography",
        _rx(
            ["biography", "biographies", "autobiography", "memoirs?", "diaries", "correspondence"],
            ["біограф", "мемуар", "спогад", "щоденник"],
        ),
    ),
    (
        "philosophy_religion",
        _rx(
            [
                "philosophy",
                "religion",
                "religious",
                "bible",
                "christian",
                "christianity",
                "theology",
                "spirituality",
                "buddhism",
                "islam",
                "ethics",
            ],
            ["філософ", "релігі", "богослов"],
        ),
    ),
    (
        "self_help",
        _rx(
            [
                "self-help",
                "self help",
                "psychology",
                "personal development",
                "success",
                "happiness",
                "motivation",
                "mindfulness",
                "parenting",
                "relationships",
            ],
            ["психолог", "саморозвит"],
        ),
    ),
    (
        "business",
        _rx(
            [
                "business",
                "economics",
                "economic",
                "management",
                "finance",
                "marketing",
                "entrepreneurship",
                "investing",
                "leadership",
            ],
            ["бізнес", "економ", "менеджмент", "фінанс"],
        ),
    ),
    (
        "technology",
        _rx(
            [
                "computers?",
                "computer science",
                "programming",
                "software",
                "technology",
                "engineering",
                "internet",
                "artificial intelligence",
            ],
            ["програмуван", "технолог", "комп'ютер"],
        ),
    ),
    # Must precede "science": "Political science" is politics, not natural science.
    ("society_politics", _rx(["political science", "social sciences?", "social science"])),
    (
        "science",
        _rx(
            [
                "science",
                "physics",
                "biology",
                "mathematics",
                "chemistry",
                "astronomy",
                "nature",
                "evolution",
                "medicine",
                "ecology",
                "genetics",
                "neuroscience",
            ],
            ["наука", "фізик", "біолог", "математ", "хімі", "медицин", "екологі"],
        ),
    ),
    (
        "history",
        _rx(
            ["history", "historical", "civilization", "archaeology", "world war", "military"],
            ["історі", "археолог"],
        ),
    ),
    (
        "society_politics",
        _rx(
            [
                "politics",
                "political",
                "sociology",
                "social",
                "law",
                "government",
                "war",
                "feminism",
                "journalism",
                "education",
            ],
            ["політик", "суспільс", "право", "соціолог"],
        ),
    ),
    (
        "arts",
        _rx(
            [
                "art",
                "arts",
                "music",
                "architecture",
                "photography",
                "film",
                "cinema",
                "design",
                "painting",
                "cooking",
                "travel",
            ],
            ["мистецтв", "музик", "архітект", "кулінар"],
        ),
    ),
    (
        "education_reference",
        _rx(
            [
                "dictionaries",
                "textbooks",
                "study and teaching",
                "grammar",
                "language",
                "encyclopedias",
                "handbooks",
                "manuals",
            ],
            ["словник", "підручник", "граматик"],
        ),
    ),
]

# A genre may have several rules; its priority is its first rule's position.
GENRE_ORDER = list(dict.fromkeys(genre for genre, _ in RULES))

# "X, fiction" subjects (places, topics) mostly say "this is fiction", not which kind, and a
# work can have dozens of them: a generic-fiction vote is worth a third of a specific one.
VOTE_WEIGHT = {"fiction": 1 / 3}

# `classics`: old general fiction (subjects rarely say so), or an explicit "classic" marker on
# a work first published long ago.
CLASSICS_BEFORE_YEAR = 1940
CLASSIC_MARKER_BEFORE_YEAR = 1960
FICTION_FOR_CLASSICS = {"fiction", "historical_fiction", "poetry_drama"}
# Genres an explicit "classic" marker may turn into `classics` (not e.g. Christie's mysteries).
CLASSIC_MARKER_GENRES = FICTION_FOR_CLASSICS | {
    "philosophy_religion",
    "society_politics",
    "history",
}
CLASSIC_MARKER = r"(?i)\bclassics?\b|classic literature|класик"

_compiled = [(genre, re.compile(pattern)) for genre, pattern in RULES]
_classic = re.compile(CLASSIC_MARKER)


def subject_genre(subject: str) -> str | None:
    """The single genre a subject votes for: the first rule it matches."""
    subject = subject.lower()
    return next((genre for genre, pattern in _compiled if pattern.search(subject)), None)


def classify(subjects: Iterable[str]) -> str | None:
    """Genre with the most subject votes (ties: earlier rule); None when nothing matches."""
    votes = Counter(g for g in map(subject_genre, subjects) if g is not None)
    if not votes:
        return None
    score = {g: n * VOTE_WEIGHT.get(g, 1.0) for g, n in votes.items()}
    return max(score, key=lambda g: (score[g], -GENRE_ORDER.index(g)))


def with_classics(
    genre: str | None, first_year: int | None, subjects: Iterable[str] = ()
) -> str | None:
    if genre is None or first_year is None:
        return genre
    if genre in FICTION_FOR_CLASSICS and first_year < CLASSICS_BEFORE_YEAR:
        return "classics"
    if (
        genre in CLASSIC_MARKER_GENRES
        and first_year < CLASSIC_MARKER_BEFORE_YEAR
        and any(_classic.search(s) for s in subjects)
    ):
        return "classics"
    return genre
