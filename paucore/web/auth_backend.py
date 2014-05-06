from django.conf import settings

from social.backends.appdotnet import AppDotNetOAuth2


class MXMLAppDotNetOAuth2(AppDotNetOAuth2):
    # TODO figure out what actual constants to distribute, we can't use PARENT_HOST here
    # AUTHORIZATION_URL = "%s/oauth/authenticate" % settings.SOCIAL_AUTH_APPDOTNET_OAUTH_BASE
    # use this one for testing login
    AUTHORIZATION_URL = "%s/oauth/authorize" % settings.SOCIAL_AUTH_APPDOTNET_OAUTH_BASE
    ACCESS_TOKEN_URL = "%s/oauth/access_token" % settings.ALPHA_API_ROOT

    def auth_headers(self):
        headers = super(MXMLAppDotNetOAuth2, self).auth_headers()
        headers['Host'] = settings.SOCIAL_AUTH_APPDOTNET_OAUTH_BASE.split('://')[1]
        return headers

    def user_data(self, access_token, *args, **kwargs):
        """Loads user data from service"""
        url = '%s/token' % settings.ALPHA_API_ROOT
        params = {
            'access_token': access_token
        }
        headers = {
            'Host': 'api.%s' % settings.PARENT_HOST
        }

        resp = self.get_json(url, params=params, headers=headers)
        resp['data']['access_token'] = access_token

        return resp

    def extra_data(self, user, uid, response, details):
        return response['data']
