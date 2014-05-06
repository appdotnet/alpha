from functools import partial

from paucore.utils.web import smart_reverse


def url_for(request):
    return {
        'url_for': partial(smart_reverse, request)
    }
