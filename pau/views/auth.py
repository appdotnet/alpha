import logging

from django.contrib.auth import logout as auth_logout, login as auth_login, REDIRECT_FIELD_NAME
from django.http import HttpResponseRedirect

from social.actions import do_complete
from social.apps.django_app.utils import strategy

from paucore.utils.web import smart_reverse

from pau.views.base import PauMMLActionView
from pau.bridge import handle_actions_blob, AlphaInsufficientStorageException


logger = logging.getLogger(__name__)


def _url_redirect_when_logged_in(request, blob_dict=None):
    if blob_dict and 'action' in blob_dict:
        try:
            handle_actions_blob(request, blob_dict)
        except AlphaInsufficientStorageException:
            logger.warning('AlphaInsufficientStorageException on handle_action_blob for login redirect  blob_dict=%s', blob_dict)


class PauLogoutView(PauMMLActionView):
    template_name = 'pau/logout.html'
    page_title = 'Log Out - Alpha'
    requires_auth = True
    page_description = 'Log Out'

    def action_logout(self, request, *args, **kwargs):
        auth_logout(request)
        return HttpResponseRedirect(smart_reverse(request, 'home'))

logout = PauLogoutView.as_view()


class PauOAuthErrorView(PauMMLActionView):
    template_name = 'pau/oauth_error.html'
    page_title = 'oAuth error - Alpha'
    requires_auth = False
    page_description = 'oAuth error'

    def populate_context(self, request, *args, **kwargs):
        super(PauOAuthErrorView, self).populate_context(request, *args, **kwargs)
        error = request.GET.get('error')
        error_description = ''
        if error == 'access_denied':
            error_description = 'You must click authorization when you are asked to authorize Alpha.'

        else:
            error_description = ('There was an during the authorization flow.'
                                 ' Please contact the site administrators and let them know.')

        self.view_ctx['error_description'] = error_description

oauth_error = PauOAuthErrorView.as_view()


@strategy('social:complete')
def complete(request, backend, *args, **kwargs):
    """Authentication complete view, override this view if transaction
    management doesn't suit your needs."""
    next_blob = request.session.pop('next_blob', None)

    error = request.GET.get('error')
    if error:
        return oauth_error(request)

    resp = do_complete(request.social_strategy, _do_login, request.user,
                       redirect_name=REDIRECT_FIELD_NAME, *args, **kwargs)

    if next_blob:
        alt_resp = _url_redirect_when_logged_in(request, next_blob)
        if alt_resp:
            return alt_resp

    return resp


def _do_login(strategy, user):
    # user.social_user is the used UserSocialAuth instance defined in
    # authenticate process
    social_user = user.social_user
    auth_login(strategy.request, user)
    strategy.request.session['OMG_NEW_TOKEN_SPOT_omo_oauth2_token'] = social_user.tokens
    if strategy.setting('SESSION_EXPIRATION', True):
        # Set session expiration date if present and not disabled
        # by setting. Use last social-auth instance for current
        # provider, users can associate several accounts with
        # a same provider.
        expiration = social_user.expiration_datetime()
        if expiration:
            try:
                strategy.request.session.set_expiry(
                    expiration.seconds + expiration.days * 86400
                )
            except OverflowError:
                # Handle django time zone overflow
                strategy.request.session.set_expiry(None)
