from typing import Annotated

from pydantic import AfterValidator, Field

from appfit.config import EMAIL_MAX_LEN, RESERVED_SLUGS, SLUG_MAX_LEN, URL_MAX_LEN

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

# Patterns also go into the OpenAPI document and are checked by Rust (pydantic) and Python code, which disagree
# on what "\s" means; so they spell out their character classes instead.
_WS = " \t\n\r\f\v"
_WS_CLASS = r"[ \t\n\r\f\v]"
_NON_WS_CLASS = r"[^ \t\n\r\f\v]"
# Every character Python's str.isspace() accepts, i.e. what str.strip() and str.split() remove.
PY_WHITESPACE = "\t\n\v\f\r\x1c\x1d\x1e\x1f \x85\xa0                　"
NOT_BLANK_PATTERN = "[^" + "".join(f"\\u{ord(c):04x}" for c in PY_WHITESPACE) + "]"
EMAIL_PATTERN = rf"^{_WS_CLASS}*[^@ \t\n\r\f\v]+@[^@ \t\n\r\f\v]+{_WS_CLASS}*$"
URL_PATTERN = rf"^{_WS_CLASS}*[Hh][Tt][Tt][Pp][Ss]?://{_NON_WS_CLASS}+{_WS_CLASS}*$"


def _email(value: str) -> str:
    """The pattern has checked the shape; strip exactly the whitespace it allowed around it."""
    return value.strip(_WS).lower()


def _url(value: str) -> str:
    return value.strip(_WS)


def _not_reserved(value: str) -> str:
    if value in RESERVED_SLUGS:
        raise ValueError(f"{value!r} is reserved")
    return value


# Lenient on purpose: internal domains such as *.local must be accepted.
Email = Annotated[str, Field(max_length=EMAIL_MAX_LEN, pattern=EMAIL_PATTERN), AfterValidator(_email)]
Url = Annotated[str, Field(max_length=URL_MAX_LEN, pattern=URL_PATTERN), AfterValidator(_url)]
Slug = Annotated[str, Field(min_length=1, max_length=SLUG_MAX_LEN, pattern=SLUG_PATTERN)]
AppSlug = Annotated[
    Slug, Field(json_schema_extra={"not": {"enum": sorted(RESERVED_SLUGS)}}), AfterValidator(_not_reserved)
]
