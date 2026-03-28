"""
Grip configuration.

Constants and defaults. User overrides go in ~/.grip/settings.py.
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

DEFAULT_GRIPHOME = "~/.grip"
DEFAULT_GRIPURL = "/__"

# -- Server defaults (overridable via ~/.grip/settings.py) --------------------

HOST = "localhost"
PORT = 6419
AUTOREFRESH = True
QUIET = False
CACHE_DIRECTORY = "cache-{version}"

# -- CDN assets ---------------------------------------------------------------

CDN_ASSETS = {
    "marked.min.js": "https://cdn.jsdelivr.net/npm/marked/marked.min.js",
    "highlight.min.js": "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/highlight.min.js",
    "github-highlight.min.css": "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/styles/github.min.css",
    "github-highlight-dark.min.css": "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/styles/github-dark.min.css",
    "mermaid.min.js": "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js",
    "github-markdown.css": "https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown.css",
}


def load_user_settings(griphome=None):
    """Load user settings from ~/.grip/settings.py.

    Returns a dict of uppercase variable names to their values.
    Only HOST, PORT, AUTOREFRESH, QUIET are recognized.
    """
    if griphome is None:
        griphome = os.environ.get("GRIPHOME", DEFAULT_GRIPHOME)
    griphome = os.path.expanduser(griphome)
    settings_file = os.path.join(griphome, "settings.py")
    if not os.path.isfile(settings_file):
        return {}
    ns = {}
    with open(settings_file) as f:
        exec(compile(f.read(), settings_file, "exec"), ns)
    return {k: v for k, v in ns.items() if k.isupper()}
