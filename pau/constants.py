
POST_LIMIT = 256
CORE_OEMBED = "net.app.core.oembed"
EXPLORE_SLUG_RE = r'[a-z0-9\-]{,255}'
USERNAME_RE = r'[A-Za-z0-9_]{1,20}'
explore_slug_url_regex = r'(?P<explore_slug>' + EXPLORE_SLUG_RE + ')'
