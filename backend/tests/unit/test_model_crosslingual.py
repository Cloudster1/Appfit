import numpy as np
import pytest

from appfit.config import Settings
from appfit.ml.embedder import build_embedder
from appfit.services.search.thresholds import thresholds_for

pytestmark = pytest.mark.model

# (requirement, capability) pairs that must reach at least "partial" with the real model.
MATCHING = [
    ("Rechnungen per OCR automatisch auslesen", "Automatic OCR extraction of invoice data from PDF"),
    ("export invoices to SAP", "Export gebuchter Rechnungen nach SAP FI"),
    ("Reisekostenabrechnung mit Belegupload", "Travel expense reports with receipt upload"),
    ("mobile app for field technicians", "Offline-fähige App für Servicetechniker"),
]
UNRELATED = [
    ("Rechnungen per OCR automatisch auslesen", "Booking of flights and hotels"),
    ("Kantinen-Speiseplan mit Allergenen", "Document archive with full text search"),
]


@pytest.fixture(scope="module")
def model():  # type: ignore[no-untyped-def]
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    return build_embedder(settings), thresholds_for(settings.embedding_model, settings)


def _sim(model, a: str, b: str) -> float:  # type: ignore[no-untyped-def]
    embedder, _ = model
    return float(np.dot(embedder.embed_queries([a])[0], embedder.embed_passages([b])[0]))


@pytest.mark.parametrize(("req", "cap"), MATCHING)
def test_cross_lingual_pairs_match(model, req: str, cap: str) -> None:  # type: ignore[no-untyped-def]
    assert _sim(model, req, cap) >= model[1].partial


@pytest.mark.parametrize(("req", "cap"), UNRELATED)
def test_unrelated_pairs_stay_below_partial(model, req: str, cap: str) -> None:  # type: ignore[no-untyped-def]
    assert _sim(model, req, cap) < model[1].partial
