from django.conf import settings
from django.contrib.auth.middleware import AuthenticationMiddleware

import adnpy


class LazyApi(object):
    migrations = set()

    def __init__(self):
        self.enabled_migrations = '&'.join('%s=1' % m for m in self.migrations)

    @staticmethod
    # stolen from paniolo
    def get_adn_api(access_token=None, headers=None):
        verify_ssl = True

        extra_headers = {
            'Host': 'api.%s' % settings.PARENT_HOST,
            'X-ADN-Proxied': '1',  # we never want to allow our server to make jsonp or CORS requests to the api
        }

        if headers:
            extra_headers.update(headers)

        return adnpy.api.build_api(api_root=settings.ALPHA_API_ROOT, access_token=access_token, verify_ssl=verify_ssl,
                                   extra_headers=extra_headers)

    def __get__(self, request, obj_type=None):
        if not request:
            return

        if not hasattr(request, '_cached_api'):
            # Build an adnpy api object. We really should save this on the request object so we're not recreating this object for every
            # api request we make in one alpha request
            try:
                token = request.session['OMG_NEW_TOKEN_SPOT_omo_oauth2_token']
            except:
                token = settings.APP_TOKEN

            headers = {
                'X-ADN-Migration-Overrides': self.enabled_migrations
            }

            api = self.get_adn_api(access_token=token, headers=headers)

            request._cached_api = api

        return request._cached_api


class AlphaAuthenticationMiddleware(AuthenticationMiddleware):
    def process_request(self, request):
        super(AlphaAuthenticationMiddleware, self).process_request(request)
        request.__class__.omo_api = LazyApi()
