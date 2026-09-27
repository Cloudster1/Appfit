"""Reject text PostgreSQL cannot store (NUL characters, lone surrogates) as a validation error, not a crash."""

import json
from collections.abc import Awaitable, Callable
from http import HTTPStatus

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from appfit.text import Loc, iter_strings, storable

JSON_MEDIA_TYPE = "application/json"


async def _texts(request: Request) -> list[tuple[Loc, str]]:
    texts: list[tuple[Loc, str]] = [(["path"], request.url.path)]
    texts += [(["query", key], key) for key in request.query_params]
    texts += [(["query", key], value) for key, value in request.query_params.multi_items()]
    if request.headers.get("content-type", "").startswith(JSON_MEDIA_TYPE):
        try:
            body = json.loads(await request.body())
        except ValueError:
            body = None  # FastAPI reports malformed bodies itself.
        texts += list(iter_strings(body, ["body"]))
    return texts


async def reject_unstorable_text(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    for loc, text in await _texts(request):
        if not storable(text):
            error = {"type": "string_unstorable", "loc": loc, "msg": "Text must not contain NUL or lone surrogates"}
            return JSONResponse({"detail": [error]}, status_code=HTTPStatus.UNPROCESSABLE_ENTITY)
    return await call_next(request)
