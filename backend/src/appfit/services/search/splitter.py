import re
from dataclasses import dataclass

from appfit.config import (
    DEFAULT_REQUIREMENT_WEIGHT,
    MAX_REQUIREMENTS,
    MIN_REQUIREMENT_WORDS,
    PRIORITY_WEIGHTS,
    SENTENCE_SPLIT_MIN_CHARS,
)
from appfit.text import normalize_ws

_KEYWORDS: dict[str, str] = {
    "must": r"must|must[- ]?haves?|muss|müssen|pflicht|zwingend|required|mandatory",
    "should": r"should|should[- ]?haves?|soll|sollte|sollen|wichtig|important",
    "could": r"could|could[- ]?haves?|nice[- ]to[- ]haves?|optional|kann|wünschenswert|wunsch",
}
_SUFFIX = r"(?:[- ]?(?:haves?|kriterien|anforderungen|requirements|features))?"
_HEADER_RES = {p: re.compile(rf"^(?:#+\s*)?(?:{kw}){_SUFFIX}\s*:?\s*$", re.IGNORECASE) for p, kw in _KEYWORDS.items()}
_PREFIX_RES = {p: re.compile(rf"^(?:{kw})\s*[:\-]\s+(?P<rest>.+)$", re.IGNORECASE) for p, kw in _KEYWORDS.items()}
_PAREN_RES = {p: re.compile(rf"[\(\[]\s*(?:{kw})\s*[\)\]]", re.IGNORECASE) for p, kw in _KEYWORDS.items()}

# Bullet glyphs pasted from Word/Confluence (bullet, middle dot, en/em dash, small square, triangle).
_BULLET_GLYPHS = re.escape("".join(chr(c) for c in (0x2022, 0x00B7, 0x2013, 0x2014, 0x25AA, 0x25B8)))
_BULLET_RE = re.compile(rf"^\s*(?:[-*+{_BULLET_GLYPHS}]|\d+[.)]|[a-zA-Z][.)]|\[[ xX]?\])\s+")
_LOW_QUOTE = re.escape(chr(0x201E))
_MD_HEADING_RE = re.compile(r"^\s*#+\s*")
_SENTENCE_SPLIT_RE = re.compile(rf"(?<=[.!?;])\s+(?=[A-ZÄÖÜ0-9\"({_LOW_QUOTE}])")
_TERMINAL_PUNCT = (".", "!", "?", ";", ":")
_ABBREVIATIONS = (
    "z.B.",
    "z. B.",
    "bzw.",
    "ca.",
    "d.h.",
    "d. h.",
    "u.a.",
    "usw.",
    "inkl.",
    "evtl.",
    "ggf.",
    "e.g.",
    "i.e.",
    "etc.",
    "vs.",
    "Nr.",
    "bspw.",
    "sog.",
)
_DOT_PLACEHOLDER = "\x00"


@dataclass
class SplitRequirement:
    text: str
    priority: str | None

    @property
    def weight(self) -> float:
        return PRIORITY_WEIGHTS[self.priority] if self.priority else DEFAULT_REQUIREMENT_WEIGHT


def _header_priority(line: str) -> str | None:
    for prio, rx in _HEADER_RES.items():
        if rx.match(line):
            return prio
    return None


def _inline_priority(line: str) -> tuple[str, str | None]:
    for prio, rx in _PREFIX_RES.items():
        m = rx.match(line)
        if m:
            return m.group("rest").strip(), prio
    for prio, rx in _PAREN_RES.items():
        if rx.search(line):
            return normalize_ws(rx.sub(" ", line)), prio
    return line, None


def _split_sentences(line: str) -> list[str]:
    protected = line
    for abbr in _ABBREVIATIONS:
        protected = protected.replace(abbr, abbr.replace(".", _DOT_PLACEHOLDER))
    parts = _SENTENCE_SPLIT_RE.split(protected)
    return [p.replace(_DOT_PLACEHOLDER, ".").strip() for p in parts if p.strip()]


def _logical_lines(text: str) -> list[tuple[str, bool]]:
    """Join soft-wrapped continuation lines; returns (line, is_bullet) pairs."""
    out: list[tuple[str, bool]] = []
    prev_blank = True
    for raw in text.replace("\r\n", "\n").split("\n"):
        if not raw.strip():
            prev_blank = True
            continue
        is_bullet = bool(_BULLET_RE.match(raw))
        line = normalize_ws(_BULLET_RE.sub("", raw, count=1))
        continuation = (
            out and not prev_blank and not is_bullet and line[:1].islower() and not out[-1][0].endswith(_TERMINAL_PUNCT)
        )
        if continuation:
            out[-1] = (f"{out[-1][0]} {line}", out[-1][1])
        else:
            out.append((line, is_bullet))
        prev_blank = False
    return out


def split_requirements(text: str) -> list[SplitRequirement]:
    """Turn free text into weighted requirements (bullets, lines, long lines split into sentences)."""
    result: list[SplitRequirement] = []
    section_priority: str | None = None
    for line, is_bullet in _logical_lines(text):
        header = _header_priority(line)
        if header is not None:
            section_priority = header
            continue
        if line.endswith(":") and not is_bullet:
            continue  # context header without priority meaning
        line = _MD_HEADING_RE.sub("", line)
        line, inline = _inline_priority(line)
        priority = inline or section_priority
        pieces = _split_sentences(line) if len(line) >= SENTENCE_SPLIT_MIN_CHARS else [line]
        first = True
        for piece in pieces:
            piece = piece.strip().rstrip(";")
            if not piece:
                continue
            is_fragment = not first and len(piece.split()) < MIN_REQUIREMENT_WORDS
            if is_fragment and result:
                result[-1].text = f"{result[-1].text} {piece}"
            else:
                result.append(SplitRequirement(piece, priority))
            first = False
    return result[:MAX_REQUIREMENTS]
