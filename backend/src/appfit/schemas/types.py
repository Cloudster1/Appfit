import re
from typing import Annotated

from pydantic import AfterValidator, Field

from appfit.config import EMAIL_MAX_LEN, SLUG_MAX_LEN, URL_MAX_LEN

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")
_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)
SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


def _email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL_RE.match(value):
        raise ValueError("not a valid email address")
    return value


def _url(value: str) -> str:
    value = value.strip()
    if not _URL_RE.match(value):
        raise ValueError("must be an http(s) URL")
    return value


# Lenient on purpose: internal domains such as *.local must be accepted.
Email = Annotated[str, Field(max_length=EMAIL_MAX_LEN), AfterValidator(_email)]
Url = Annotated[str, Field(max_length=URL_MAX_LEN), AfterValidator(_url)]
Slug = Annotated[str, Field(min_length=1, max_length=SLUG_MAX_LEN, pattern=SLUG_PATTERN)]
