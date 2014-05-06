import logging
from functools import partial
from datetime import datetime

from django.conf import settings

from paucore.utils.date import datetime_to_secs
from paucore.utils.web import smart_reverse

logger = logging.getLogger(__name__)


def url_for(request):
    return {
        'url_for': partial(smart_reverse, request)
    }


def default_jscontext(request):
    context = {}

    user = getattr(request, 'user', None)
    if user and user.is_authenticated():
        context['__js_is_authenticated'] = True
        context['__js_authenticated_user_id'] = user.pk
    else:
        context['__js_is_authenticated'] = False

    if hasattr(request, 'unique_id'):
        context['__js_cookie_value'] = request.unique_id.cookie_value

    context['__js_timestamp'] = datetime_to_secs(datetime.now()) * 1000
    context['__js_build_info'] = settings.BUILD_INFO

    context['is_pjax'] = request.META.get('HTTP_X_PJAX')
    context['__js_is_pjax'] = request.META.get('HTTP_X_PJAX')
    context['get_asset_url'] = lambda _, x: x
    return context
