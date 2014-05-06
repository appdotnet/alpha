import logging
import urllib

from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.encoding import smart_str

from paucore.utils.python import lru_cache

logger = logging.getLogger(__name__)


def smart_urlencode(params, force_percent=False):
    if force_percent:
        qf = urllib.quote
    else:
        qf = urllib.quote_plus

    parts = ('='.join((qf(smart_str(k)), qf(smart_str(v)))) for k, v in params.iteritems())

    return '&'.join(parts)


def append_query_string(url, params=None, force_percent=False):
    if not params:
        return url

    parts = [url]
    if '?' in url:
        parts.append('&')
    else:
        parts.append('?')

    parts.append(smart_urlencode(params, force_percent=force_percent))

    return ''.join(parts)


def memoized_reverse(viewname, urlconf=None, args=None, kwargs=None, prefix=None, current_app=None):
    args = args or ()
    kwargs = kwargs or {}

    # make these hashable
    memo_args = (viewname, urlconf, tuple(args), tuple(kwargs.iteritems()), prefix, current_app)

    try:
        hash(memo_args)
    except:
        # Shouldn't get called, but log and don't fail if it does
        logger.warning('memoized_reverse() called with unhashable args: %s', memo_args)

        return reverse(viewname, urlconf=urlconf, args=args, kwargs=kwargs, prefix=prefix, current_app=current_app)

    return _wrapped_reverse(memo_args)


@lru_cache(maxsize=10240)
def _wrapped_reverse(memo_args):
    viewname, urlconf, args, kwargs, prefix, current_app = memo_args

    return reverse(viewname, urlconf=urlconf, args=args, kwargs=dict(kwargs), prefix=prefix, current_app=current_app)


def smart_reverse(request, view, args=None, kwargs=None, force_qualified=False, url_params=None, url_fragment=None):
    view_path = memoized_reverse(view, args=args, kwargs=kwargs)

    # want SSL if: host requires SSL or is_ssl is set
    # or if we're on an SSL link and is_ssl was not supplied
    is_ssl = (request and request.is_secure()) or settings.SSL_ONLY

    # want scheme if:
        # is_ssl and !request.is_secure()
        # !is_ssl and request.is_secure()

    parts = []

    if force_qualified or not request or is_ssl != request.is_secure():
        if is_ssl:
            parts.append('https:')
        else:
            parts.append('http:')

    if parts:
        parts.append('//')
        parts.append(settings.PARENT_HOST)

    parts.append(view_path)

    if url_params:
        parts.append('?')
        parts.append(smart_urlencode(url_params))

    if url_fragment:
        parts.append('#')
        parts.append(url_fragment)

    return ''.join(parts)
