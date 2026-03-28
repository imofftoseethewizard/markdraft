"""
Markdraft configuration.

Constants and defaults. User overrides go in ~/.markdraft/settings.py.
"""

import os

# -- Readme file discovery ---------------------------------------------------

SUPPORTED_TITLES = ["README", "Readme", "readme", "Home"]
SUPPORTED_EXTENSIONS = [".md", ".markdown"]

DEFAULT_FILENAMES = [
    title + ext for title in SUPPORTED_TITLES for ext in SUPPORTED_EXTENSIONS
]
DEFAULT_FILENAME = DEFAULT_FILENAMES[0]

# -- Paths and URLs -----------------------------------------------------------

DEFAULT_CONFIG_HOME = "~/.markdraft"
DEFAULT_URL_PREFIX = "/__"

# -- Server defaults (overridable via ~/.markdraft/settings.py) ---------------

HOST = "localhost"
PORT = 6419
AUTOREFRESH = True
QUIET = False
CACHE_DIRECTORY = "cache-{version}"

# -- CDN assets ---------------------------------------------------------------

CDN_ASSETS = {
    # Markdown rendering
    "marked.min.js": "https://cdn.jsdelivr.net/npm/marked/marked.min.js",
    # Syntax highlighting
    "highlight.min.js": "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/highlight.min.js",
    "github-highlight.min.css": "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/styles/github.min.css",
    "github-highlight-dark.min.css": "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/styles/github-dark.min.css",
    # Mermaid diagrams
    "mermaid.min.js": "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js",
    # GitHub styling
    "github-markdown.css": "https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown.css",
    # Math (LaTeX) rendering
    "katex.min.js": "https://cdn.jsdelivr.net/npm/katex@0.16/dist/katex.min.js",
    "marked-katex-extension.umd.js": "https://cdn.jsdelivr.net/npm/marked-katex-extension",
    # GitHub-style alerts ([!NOTE], [!WARNING], etc.)
    "marked-alert.umd.js": "https://cdn.jsdelivr.net/npm/marked-alert",
    # GeoJSON map rendering
    "leaflet.js": "https://cdn.jsdelivr.net/npm/leaflet@1/dist/leaflet.js",
    "leaflet.css": "https://cdn.jsdelivr.net/npm/leaflet@1/dist/leaflet.css",
    # STL 3D model rendering
    "three.min.js": "https://cdn.jsdelivr.net/npm/three@0.170/build/three.min.js",
}

# KaTeX CSS is loaded from CDN directly (references relative font URLs
# that the CDN serves automatically). Not cached locally.
KATEX_CSS_URL = "https://cdn.jsdelivr.net/npm/katex@0.16/dist/katex.min.css"


def load_user_settings(config_home: str | None = None) -> dict[str, object]:
    """Load user settings from ~/.markdraft/settings.py.

    Returns a dict of uppercase variable names to their values.
    Only HOST, PORT, AUTOREFRESH, QUIET are recognized.
    """
    if config_home is None:
        config_home = os.environ.get("MARKDRAFT_HOME", DEFAULT_CONFIG_HOME)
    config_home = os.path.expanduser(config_home)
    settings_file = os.path.join(config_home, "settings.py")
    if not os.path.isfile(settings_file):
        return {}
    ns: dict[str, object] = {}
    with open(settings_file) as f:
        exec(compile(f.read(), settings_file, "exec"), ns)
    return {k: v for k, v in ns.items() if k.isupper()}
