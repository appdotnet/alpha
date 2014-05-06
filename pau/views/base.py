import logging

from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.http import HttpResponseRedirect

from paucore.utils.web import smart_reverse
from paucore.web.template import render_template_response
from paucore.web.views import MMLActionView

from pau import bridge

from pau.forms import ReportPostForm
from pau.views.mixins import OAuthLoginRequiredViewMixin

logger = logging.getLogger(__name__)


def rate_limit_handler(request, *args, **kwargs):
    response = render_template_response(request, {}, '429.html')
    response.status_code = 429
    return response


class PauMMLActionView(OAuthLoginRequiredViewMixin, MMLActionView):
    selected_nav_page = None
    minify_html = False

    def populate_context(self, request, *args, **kwargs):
        super(PauMMLActionView, self).populate_context(request, *args, **kwargs)
        self.view_ctx.update_ctx({
            '__js_page_load_hooks': ['utils.handle_resize', 'init_pau', 'init_post_delete', 'init_mute_user', 'init_post_report',
                                     'init_star_post', 'init_repost', 'pau.init_fixed_nav'],
            '__js_api_options': {
                'api_base_url': smart_reverse(request, 'omo_api_proxy'),
            },
            '__js_canvas_mode': 'pau',
            '__js_subscribe_url': 'https://account.app.net/upgrade/',
            '__js_upgrade_storage_url': 'https://account.app.net/settings/upgrade/storage/',
            'selected_nav_page': self.selected_nav_page,
            'explore_streams': bridge.list_explore_streams(request),
            'report_post_form': ReportPostForm(),
        })

        self.view_ctx.forms = []

    def dispatch(self, request, *args, **kwargs):
        try:
            response = super(PauMMLActionView, self).dispatch(request, *args, **kwargs)
        except bridge.AlphaRateLimitAPIException, e:
            logger.warn('Hit an api rate limit: %s', e)
            return rate_limit_handler(request, *args, **kwargs)
        except bridge.AlphaAuthAPIException, e:
            logger.info('Alpha auth API execption: %s', e)
            auth_logout(request)
            return HttpResponseRedirect('/')

        response['X-Build-Info'] = settings.BUILD_INFO

        return response
