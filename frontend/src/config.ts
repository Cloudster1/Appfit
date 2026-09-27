// Tunable UI constants, kept in one place.
export const APP_TITLE = "Appfit";
export const API_CSRF_HEADER = { "X-Requested-With": "XMLHttpRequest" } as const;

export const PAGE_SIZE = 25;
// Divisible by 2 and 3 so full grid rows stay full.
export const CATALOG_PAGE_SIZE = 24;
export const ALL_APPS_PAGE_SIZE = 200;
export const SEARCH_RESULT_LIMIT = 10;
export const MATRIX_TOP_APPS = 5;
export const LIST_SEARCH_DEBOUNCE_MS = 300;
export const EMBEDDING_POLL_MS = 3000;
export const QUERY_STALE_MS = 30_000;
export const CAPABILITY_ATOMIC_WARN_LEN = 200;
export const SHORT_DESCRIPTION_MAX_LEN = 300;
export const PASSWORD_MIN_LEN = 10;
export const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
export const PERCENT = 100;
export const SIMILAR_APPS_LIMIT = 5;
export const RECENT_LOGS_LIMIT = 25;
export const MAX_RESULT_TAGS = 8;
export const DEV_WATCH_POLL_MS = 300;

// Layout and icon sizes (px)
export const ICON_SIZE = { xs: 14, sm: 16, md: 18, lg: 22, xl: 32 } as const;
export const LOGO_SIZE = 26;
export const HEADER_HEIGHT = 56;
export const TOOLTIP_MAX_WIDTH = 320;
export const NARROW_FORM_WIDTH = 520;
export const CONTENT_MAX_WIDTH = 1100;
export const PORTAL_MAX_WIDTH = 1280;
export const FACET_VISIBLE_VALUES = 8;
export const TILE_RING_SIZE = 52;
export const TILE_RING_THICKNESS = 5;
export const TILE_DESCRIPTION_LINES = 3;
export const TILE_MAX_TAGS = 3;
export const TILE_AVATAR_SIZE = 40;
export const OWNER_AVATAR_SIZE = 22;
export const REQUIREMENT_DOT_SIZE = 9;
export const MATRIX_REQUIREMENT_WIDTH = 260;
export const INTRO_MAX_WIDTH = 720;
export const HINT_MAX_WIDTH = 640;
export const SORT_SELECT_WIDTH = 170;
// Spacing (px) below Mantine's smallest token, for dense rows such as dots and labels.
export const GAP_TIGHT = 4;
export const GAP_COMPACT = 6;
export const DRAWER_WIDTH = 560;
export const MOBILE_NAV_WIDTH = 260;
export const TABLE_MIN_WIDTH = 800;
export const DROPZONE_MIN_HEIGHT = 120;
export const MAX_UPLOAD_BYTES = 10_000_000;
export const NAME_COLUMN_MAX_WIDTH = 380;

export const DEFAULT_SEARCH_LIFECYCLE = ["idea", "pilot", "active", "deprecated"] as const;

export const MATRIX_CSV_DELIMITER = ";";
export const RESULTS_VIEW_STORAGE_KEY = "appfit-results-view";

export const STATUS_COLORS = {
  covered: "green",
  partial: "yellow",
  gap: "red",
} as const;

export const LABEL_COLORS = {
  strong: "green",
  partial: "yellow",
  weak: "gray",
} as const;

export const LIFECYCLE_COLORS: Record<string, string> = {
  idea: "grape",
  pilot: "cyan",
  active: "teal",
  deprecated: "orange",
  retired: "gray",
};

export const PRIORITY_LABELS: Record<string, string> = {
  must: "Must",
  should: "Should",
  could: "Could",
};

// Interfaces and the landscape graph
export const INTERFACE_TYPE_LABELS: Record<string, string> = {
  rest_api: "REST API",
  soap: "SOAP",
  file_transfer: "File transfer",
  database: "Database",
  messaging: "Messaging / events",
  sso: "SSO / identity",
  ui_embedding: "UI embedding",
  other: "Other",
};
export const INTERFACE_TYPE_COLORS: Record<string, string> = {
  rest_api: "blue",
  soap: "indigo",
  file_transfer: "orange",
  database: "grape",
  messaging: "teal",
  sso: "pink",
  ui_embedding: "cyan",
  other: "gray",
};
export const INTERFACE_STATUS_LABELS: Record<string, string> = {
  planned: "Planned",
  active: "Active",
  deprecated: "Deprecated",
};
export const INTERFACE_FREQUENCY_LABELS: Record<string, string> = {
  realtime: "Real-time",
  batch: "Batch",
  on_demand: "On demand",
};
export const GRAPH_NODE_WIDTH = 164;
export const GRAPH_NODE_HEIGHT = 44;
export const GRAPH_LAYER_SPACING = 70;
export const GRAPH_NODE_SPACING = 20;
export const GRAPH_EDGE_WIDTH = 1.6;
export const GRAPH_DIMMED_OPACITY = 0.15;
export const GRAPH_DEPRECATED_OPACITY = 0.45;
export const LANDSCAPE_HEIGHT = "calc(100dvh - 230px)";
export const GRAPH_FIT_MAX_ZOOM = 1;
export const GRAPH_FOCUS_DURATION_MS = 300;
// Lets the graph container settle (e.g. after the details panel opens) before fitting the view.
export const GRAPH_FIT_DELAY_MS = 60;
export const LANDSCAPE_MIN_HEIGHT = 480;
export const MINI_GRAPH_HEIGHT = 320;
export const SMALL_GRAPH_HEIGHT = 180;
export const SMALL_GRAPH_MAX_NODES = 4;
export const FIT_VIEW_PADDING = 0.15;
export const GRAPH_MIN_ZOOM = 0.2;
