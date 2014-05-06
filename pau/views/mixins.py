import logging

from django.http import HttpResponseRedirect

from paucore.utils.web import smart_reverse
from paucore.web.views import ViewMiddleware, EarlyReturn

logger = logging.getLogger(__name__)


class OAuthLoginRequiredViewMixin(ViewMiddleware):
    requires_auth = True

    def process_pre_view(self, view_inst):
        # duplicated with enforce_auth so that requires_auth can vary based on the view_inst
        if view_inst.requires_auth and not self.is_authorized(view_inst.state.request):
            self.raise_not_authorized(view_inst.state.request, *view_inst.state.view_args, **view_inst.state.view_kwargs)

    def is_authorized(self, request, *args, **kwargs):
        return request.user.is_authenticated()

    def next_url(self, request):
        return request.build_absolute_uri()

    def handle_not_authorized(self, request, *args, **kwargs):
        return HttpResponseRedirect(smart_reverse(request, 'login', url_params={'next': self.next_url(request)}))

    def raise_not_authorized(self, request, *args, **kwargs):
        resp = self.handle_not_authorized(request, *args, **kwargs)
        raise EarlyReturn(resp)

    def enforce_auth(self, request, *args, **kwargs):
        if self.requires_auth and not self.is_authorized(request):
            # this is how we "decorate" for login_required
            self.raise_not_authorized(request, *args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        try:
            self.enforce_auth(request, *args, **kwargs)
        except EarlyReturn, er:
            return er.response
        return super(OAuthLoginRequiredViewMixin, self).dispatch(request, *args, **kwargs)
