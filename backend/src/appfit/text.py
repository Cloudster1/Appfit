import hashlib
import re
import unicodedata
from functools import lru_cache

import snowballstemmer

from appfit.config import MIN_CONTENT_TOKEN_LEN, STEM_CACHE_SIZE

_WS_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[^\W_]+(?:[-.][^\W_]+)*", re.UNICODE)

STOPWORDS_EN = frozenset(
    """a about above after again all also am an and any are as at be because been before being below between
    both but by can could did do does doing down during each few for from further had has have having he her
    here hers him his how i if in into is it its itself just me more most must my no nor not now of off on
    once only or other our ours out over own same shall she should so some such than that the their theirs
    them then there these they this those through to too under until up very via was we were what when where
    which while who whom why will with within without would you your yours able need needs needed want wants
    using use used support supports supported provide provides allow allows etc e.g i.e""".split()
)

STOPWORDS_DE = frozenset(
    """aber alle allem allen aller alles als also am an ander andere anderem anderen anderer anderes anderm
    andern anderr anders auch auf aus bei bin bis bist da damit dann das dass dasselbe dazu dein deine
    deinem deinen deiner deines dem demselben den denn denselben der derer derselbe derselben des desselben
    dessen dich die dies diese dieselbe dieselben diesem diesen dieser dieses dir doch dort du durch ein
    eine einem einen einer eines einig einige einigem einigen einiger einiges einmal er es etwas euch euer
    eure eurem euren eurer eures für gegen gewesen hab habe haben hat hatte hatten hier hin hinter ich ihm
    ihn ihnen ihr ihre ihrem ihren ihrer ihres im in indem ins ist jede jedem jeden jeder jedes jene jenem
    jenen jener jenes jetzt kann kein keine keinem keinen keiner keines können könnte machen man manche
    manchem manchen mancher manches mein meine meinem meinen meiner meines mich mir mit muss musste nach
    nicht nichts noch nun nur ob oder ohne sehr sein seine seinem seinen seiner seines selbst sich sie sind
    so solche solchem solchen solcher solches soll sollen sollte sondern sonst über um und uns unsere
    unserem unseren unser unseres unter viel vom von vor während war waren warst was weg weil weiter welche
    welchem welchen welcher welches wenn werde werden wie wieder will wir wird wirst wo wollen wollte würde
    würden zu zum zur zwar zwischen sowie bzw z.b ca usw inkl d.h u.a möglich muss müssen soll sollte
    unterstützung unterstützen unterstützt bereitstellen""".split()
)

STOPWORDS = STOPWORDS_EN | STOPWORDS_DE

_stemmer_de = snowballstemmer.stemmer("german")
_stemmer_en = snowballstemmer.stemmer("english")


def normalize_ws(text: str) -> str:
    return _WS_RE.sub(" ", unicodedata.normalize("NFC", text)).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(unicodedata.normalize("NFC", text))]


def content_tokens(text: str) -> list[str]:
    return [t for t in tokenize(text) if t not in STOPWORDS and len(t) >= MIN_CONTENT_TOKEN_LEN and not t.isdigit()]


@lru_cache(maxsize=STEM_CACHE_SIZE)
def stems(token: str) -> frozenset[str]:
    """German and English stems of one token, so mixed-language text still overlaps."""
    return frozenset({_stemmer_de.stemWord(token), _stemmer_en.stemWord(token)})


def stem_map(text: str) -> dict[str, set[str]]:
    """Map every content stem of the text to the surface tokens it came from."""
    out: dict[str, set[str]] = {}
    for tok in content_tokens(text):
        for s in stems(tok):
            out.setdefault(s, set()).add(tok)
    return out
