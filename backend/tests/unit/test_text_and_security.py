import uuid

import numpy as np

from appfit.auth.security import create_access_token, decode_access_token, hash_password, verify_password
from appfit.config import Settings
from appfit.ml.fake_embedder import FakeEmbedder
from appfit.text import content_tokens, stem_map


def test_content_tokens_drop_stopwords_in_both_languages() -> None:
    assert content_tokens("Die Anwendung muss den Export nach SAP unterstützen") == ["anwendung", "export", "sap"]
    assert content_tokens("The system must allow a PDF export") == ["system", "pdf", "export"]


def test_stems_overlap_across_inflections() -> None:
    a = stem_map("Rechnungen freigeben")
    b = stem_map("Freigabe von Rechnung")
    assert "rechnung" in a.keys() & b.keys()


def test_fake_embedder_is_deterministic_normalized_and_lexical() -> None:
    e = FakeEmbedder()
    v = e.embed_passages(["single sign-on with Azure AD", "Azure AD single sign-on", "PDF export"])
    assert v.shape == (3, 1024)
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)
    assert np.allclose(v, e.embed_passages(["single sign-on with Azure AD", "Azure AD single sign-on", "PDF export"]))
    assert v[0] @ v[1] > 0.9
    assert v[0] @ v[2] < 0.2


def test_password_hashing() -> None:
    h = hash_password("s3cret-password")
    assert verify_password("s3cret-password", h)
    assert not verify_password("wrong", h)
    assert not verify_password("anything", None)


def test_jwt_roundtrip_and_tamper_detection() -> None:
    settings = Settings(_env_file=None, jwt_secret="a" * 40)  # type: ignore[call-arg]
    uid = uuid.uuid4()
    token = create_access_token(uid, "editor", settings)
    payload = decode_access_token(token, settings)
    assert payload is not None and payload["sub"] == str(uid) and payload["role"] == "editor"
    other = Settings(_env_file=None, jwt_secret="b" * 40)  # type: ignore[call-arg]
    assert decode_access_token(token, other) is None
    assert decode_access_token(token + "x", settings) is None
