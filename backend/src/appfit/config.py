from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Fixed by the vector(N) columns in migration 0003. Changing it needs a new migration.
EMBEDDING_DIM = 1024
HNSW_M = 16
HNSW_EF_CONSTRUCTION = 64
HNSW_EF_SEARCH = 100

# Field length limits, shared by DB columns and API validation.
ENUM_MAX_LEN = 16
EMAIL_MAX_LEN = 320
NAME_MAX_LEN = 200
SLUG_MAX_LEN = 120
SHORT_DESCRIPTION_MAX_LEN = 300
DESCRIPTION_MAX_LEN = 20_000
CAPABILITY_TEXT_MAX_LEN = 500
CAPABILITY_DETAILS_MAX_LEN = 4000
URL_MAX_LEN = 1000
SHORT_TEXT_MAX_LEN = 120
IDENT_MAX_LEN = 255
PROVIDER_MAX_LEN = 32
INTERFACE_DESCRIPTION_MAX_LEN = 4000
INTERFACE_MAX_DATA_OBJECTS = 30
HASH_LEN = 64
PASSWORD_MIN_LEN = 10
PASSWORD_MAX_LEN = 256

# Heuristic for the editor warning "capability is not atomic".
CAPABILITY_ATOMIC_WARN_LEN = 200

# Paging
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 200

# Search input
MAX_SEARCH_TEXT_LEN = 20_000
MAX_REQUIREMENTS = 30
SEARCH_DEFAULT_LIMIT = 10
MAX_SEARCH_LIMIT = 50
NO_MATCH_CLOSEST = 3
MAX_COMBINATIONS = 3
# Results scoring below this fraction of the best result are hidden (long tail of generic matches).
MIN_RELATIVE_SCORE = 0.5
SENTENCE_SPLIT_MIN_CHARS = 120
MIN_REQUIREMENT_WORDS = 3
PRIORITY_WEIGHTS = {"must": 1.0, "should": 0.6, "could": 0.3}
DEFAULT_REQUIREMENT_WEIGHT = 1.0

# Retrieval
SUMMARY_TOP_K = 50
CAPABILITY_TOP_K_PER_REQ = 30
FTS_TOP_K = 50
RETRIEVAL_LISTS = 3

# Scoring
SCORE_WEIGHT_COVERAGE = 0.60
SCORE_WEIGHT_SOFT = 0.30
SCORE_WEIGHT_RETRIEVAL = 0.10
PARTIAL_CREDIT = 0.5
MUST_GAP_PENALTY = 0.75
SUMMARY_CAP_MARGIN = 0.001
SOFT_FLOOR_OFFSET = 0.10
LABEL_STRONG_COVERAGE = 0.75
LABEL_PARTIAL_COVERAGE = 0.40
SIMILAR_APPS_LIMIT = 5
SCORE_DECIMALS = 4
RRF_DECIMALS = 5

# Evaluation sweeps: (start, stop, step) for numpy.arange
EVAL_SIMILARITY_GRID = (0.40, 0.95, 0.01)
EVAL_NOMATCH_GRID = (0.20, 0.71, 0.02)
EVAL_TOP_COVERAGE_GRID = (0.20, 0.61, 0.02)
EVAL_COVERED_MIN_PRECISION = 0.75

# Import / export
IMPORT_FORMAT_VERSION = 1
CSV_MULTI_VALUE_SEPARATOR = "|"
CSV_SNIFF_BYTES = 64_000

# Text analysis
MIN_CONTENT_TOKEN_LEN = 2
STEM_CACHE_SIZE = 65536
FAKE_EMBEDDER_TRIGRAM_WEIGHT = 0.3


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = "postgresql+psycopg://appfit:appfit@localhost:5432/appfit"

    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 480
    cookie_name: str = "appfit_session"
    cookie_secure: bool = False
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None

    embedding_backend: Literal["sentence_transformers", "fake"] = "sentence_transformers"
    embedding_model: str = "BAAI/bge-m3"
    embedding_model_revision: str | None = None
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32
    embedding_max_seq_length: int = 512

    embed_worker_enabled: bool = True
    embed_worker_poll_seconds: float = 5.0
    embed_worker_batch_size: int = 64

    # Matching. Thresholds default to the per-model values in thresholds.yaml.
    match_t_covered: float | None = None
    match_t_partial: float | None = None
    match_t_nomatch: float | None = None
    match_candidates: int = 40
    rrf_k: int = 60
    lexical_bonus: float = 0.03
    search_log_enabled: bool = True

    import_max_bytes: int = 10_000_000
    import_max_apps: int = 5000

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
