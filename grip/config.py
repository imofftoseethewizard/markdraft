"""
Grip configuration.

Constants and Flask default settings in one place. User overrides go in
~/.grip/settings.py or a local settings_local.py, which Flask loads on
top of these defaults.
"""

# -- Readme file discovery ---------------------------------------------------

SUPPORTED_TITLES = ['README', 'Readme', 'readme', 'Home']
SUPPORTED_EXTENSIONS = ['.md', '.markdown']

DEFAULT_FILENAMES = [title + ext
                     for title in SUPPORTED_TITLES
                     for ext in SUPPORTED_EXTENSIONS]
DEFAULT_FILENAME = DEFAULT_FILENAMES[0]

# -- Paths and URLs -----------------------------------------------------------

DEFAULT_GRIPHOME = '~/.grip'
DEFAULT_GRIPURL = '/__/grip'
DEFAULT_API_URL = 'https://api.github.com'

# -- Flask settings (overridable via ~/.grip/settings.py) ---------------------

HOST = 'localhost'
PORT = 6419
DEBUG = False
DEBUG_GRIP = False
CACHE_DIRECTORY = 'cache-{version}'
AUTOREFRESH = True
QUIET = False

USERNAME = None
PASSWORD = None
API_URL = None
STYLE_URLS = []

# -- Style and asset scraping -------------------------------------------------

STYLE_URLS_SOURCE = 'https://github.com/joeyespo/grip'
STYLE_URLS_RES = [
    r'''<link\b[^>]+\bhref=['"]?([^'" >]+)['"]?\brel=['"]?stylesheet['"]?[^>]+[^>]*(?=>)''',
    r'''<link\b[^>]+\brel=['"]?stylesheet['"]?[^>]+\bhref=['"]?([^'" >]+)['"]?[^>]*(?=>)''',
]
STYLE_ASSET_URLS_RE = (
    r'''url\(['"]?(/static/fonts/octicons/[^'" \)]+)['"]?\)''')
STYLE_ASSET_URLS_SUB_FORMAT = r'url("{0}\1")'
STYLE_ASSET_URLS_INLINE_FORMAT = (
    r'''url\(['"]?((?:/static|{0})/[^'" \)]+)['"]?\)''')

# -- Mermaid ------------------------------------------------------------------

MERMAID_JS_URL = (
    'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js')
