"""Search text for a printed name: every way a visitor may type it (lemko/spec/data-audit,
findings normalize-03, normalize-05 and normalize-08).

The printed name is never changed. evicted_persons.name_search holds, for searching only:
- the name normalized: lower case; apostrophes, combining marks, '?' and '*' dropped; brackets and
  punctuation turned into spaces ("Бондар (Гондар) Марія" -> бондар гондар марія);
- for a bracket inside a word or right after it, every reading the bracket allows: the word without
  the bracket, the bracket's letters replacing as many letters before it, and the bracket's letters
  inserted ("Ко(а)чмарчик" -> кочмарчик, качмарчик, коачмарчик; "Палко(в)?" -> палко, палкв, палков;
  "Тим(офійович)" -> тим, тимофійович);
- a word split by a space joined again ("Марі я" -> марія), and words glued together split
  ("БарнякАндрій" -> барняк андрій);
- for a surname the book prints in both genders, the other form ("Криницька" -> криницький), from
  app/data/surname_pairs.csv, which lists only the pairs the book itself prints.
The query gets the same normalization, and each of its words must be a substring of name_search.
"""
import csv
import itertools
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

APOSTROPHES = "'’ʼ‘`"
UPPER = 'А-ЯІЇЄҐ'
LOWER = 'а-яіїєґ'
LETTERS = f'{UPPER}{LOWER}A-Za-z{APOSTROPHES}'
SURNAME_PAIRS = Path(__file__).resolve().parent / 'data' / 'surname_pairs.csv'
SPLIT_WORD_EXCEPTIONS = {'і', 'й', 'та', 'д', 'с', 'син', 'дочка', 'донька'}
# Notes printed in brackets are not readings of a word
NOTE = re.compile(r'\d|№|\bдо\s|заклеєн|розмит|обірван|обрізан|нерозбірл|пошкоджен|відірван', re.IGNORECASE)


def normalize(text):
    """Lower case, NFC, no apostrophes or combining marks, no '?' or '*', punctuation to spaces."""
    s = unicodedata.normalize('NFC', text or '').lower()
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(rf'\s*[{APOSTROPHES}]\s*', '', s)  # "Дем' янович" -> демянович
    s = s.replace('–', '-').replace('—', '-')
    s = re.sub(r'[?*]', '', s)
    s = re.sub(r'[()\[\]{}.,/\\:;"«»]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


@lru_cache(maxsize=1)
def surname_pairs():
    """Normalized surname -> the other gender's form(s), as printed in the book."""
    pairs = {}
    with open(SURNAME_PAIRS, encoding='utf-8', newline='') as fh:
        for r in csv.DictReader(fh):
            feminine, masculine = normalize(r['feminine']), normalize(r['masculine'])
            pairs.setdefault(feminine, set()).add(masculine)
            pairs.setdefault(masculine, set()).add(feminine)
    return pairs


def _letter_level(content, glued_left, glued_right, next_char):
    """Whether a bracket offers another reading of the word it stands in ('Ко(а)чмарчик'), and how.
    Follows the data audit's parser (spec/data-audit/tools/normalize/namelib.py, classify_paren)."""
    alt = content.strip('? ')
    if not alt or NOTE.search(content) or not re.fullmatch(rf'[{LETTERS}]+', alt):
        return None  # notes, years, cross-references, several words: the normalized text covers them
    lower = alt[0].islower()
    if glued_left and glued_right and not (alt[0].isupper() and len(alt) > 1 and next_char.isupper()):
        return 'inside'          # Фо(а)тія, Королі(Круле)вський
    if lower and glued_right:
        return 'inside'          # Кош (с?)тишак
    if lower and glued_left:
        return 'completion' if len(alt) >= 4 else 'end'   # Тим(офійович), Палко(в)?
    if lower and len(alt) <= 4:
        return 'end'             # Дзюрбіль (нь?)
    if glued_left and len(alt) == 1:
        return 'end'             # Л(М?) абовський
    return None                  # a separate word in brackets ("Бондар (Гондар)"): a word of its own


def _choices(content, kind):
    """How a letter-level bracket may change its word (namelib.letter_candidates): (how, letters)."""
    alt = content.strip('? ')
    if kind == 'completion':
        return [('insert', alt)]                     # Тим(офійович) -> Тимофійович
    if alt[0].isupper() and len(alt) > 1:
        return [('replace_all', alt)]                # Королі(Круле)вський -> Крулевський
    if alt[0].isupper():
        return [('replace', alt)]                    # Л(М?)абовський -> Мабовський (one letter)
    return [('replace', alt), ('insert', alt)]       # Фо(а)тія -> Фатія; Палко(в) -> Палков


def _spell(segments, picks):
    """Build a word from its text segments and one choice per bracket between them."""
    built = segments[0]
    for (how, alt), segment in zip(picks, segments[1:]):
        if how == 'insert':
            built += alt
        elif how == 'replace':
            built = (built[:-len(alt)] if len(built) >= len(alt) else '') + alt
        elif how == 'replace_all':
            built = alt
        built += segment
    return built


def _readings(text):
    """The words of the name read without its brackets (split words joined, glued words split), and
    every other reading its letter-level brackets allow. Returns (main words, other readings)."""
    brackets, core, last = [], '', 0
    for m in re.finditer(r'\(([^()]*)\)', text):
        start, end = m.start(), m.end()
        before = text[start - 1] if start > 0 else ' '
        after = text[end] if end < len(text) else ' '
        kind = _letter_level(m.group(1), before != ' ', after not in ' ,.?)', after)
        core += text[last:start]
        if kind:
            brackets.append((m.group(1), kind))
            core += f'⁅{len(brackets) - 1}⁆'  # keeps the bracket's place inside its word
        else:
            core += ' '
        last = end
    core += text[last:]
    joined = []
    for tok in core.replace(',', ' ').split():
        if joined and (tok.startswith('⁅') or joined[-1][-1] in APOSTROPHES):
            joined[-1] += tok                                        # "Кош (с?)тишак", "Дем' янович"
        elif joined and re.match(rf'[{LOWER}]', tok) and tok.lower() not in SPLIT_WORD_EXCEPTIONS:
            joined[-1] += tok                                        # "Марі я", "Ко(а) бан"
        else:
            joined.append(tok)
    main, others = [], []
    for tok in joined:
        segs = re.split(r'⁅(\d+)⁆', tok)
        texts = [s.replace('?', '') for s in segs[0::2]]
        word = ''.join(segs[0::2])
        # every combination of the brackets' readings: Ску(о)чипец(ь) -> скочипець as well
        options = [[('none', '')] + _choices(*brackets[int(i)]) for i in segs[1::2]]
        for picks in itertools.product(*options):
            if any(how != 'none' for how, _ in picks):
                others.append(_spell(texts, picks))
        for part in re.split(rf'(?<=[{LOWER}?])(?=[{UPPER}])', word):   # "БарнякАндрійСтепанович"
            if part:
                main.append(part)
    return main, others


def name_search(full_name):
    """Every way to type a printed name, normalized, without repeated words."""
    if not full_name:
        return ''
    main, others = _readings(full_name)
    words = []
    for word in normalize(' '.join([full_name] + main + others)).split():
        if word not in words:
            words.append(word)
    # the other gender's form of the surname, for the surname and its other readings
    pairs = surname_pairs()
    first = normalize(main[0]).split()[:1] if main else []
    surnames = first + [w for w in normalize(' '.join(others)).split() if first and w[:2] == first[0][:2]]
    for surname in surnames:
        for other in sorted(pairs.get(surname, ())):
            if other not in words:
                words.append(other)
    return ' '.join(words)


def query_words(query):
    """The words of a search query, normalized like name_search."""
    return normalize(query).split()
