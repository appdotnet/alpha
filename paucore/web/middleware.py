from django.conf import settings


class NullSessionBackend(dict):
    def flush(self):
        self.clear()

    def cycle_key(self):
        self.clear()


class NoCacheMiddleware(object):

    def process_response(self, request, response):
        if request.user.is_authenticated():
            response['Cache-control'] = 'private, no-cache, no-store, must-revalidate'
            response['Expires'] = 'Thu, 9 Sep 1999 09:09:09 GMT'
            response['Pragma'] = 'no-cache'
        elif settings.DEBUG:
            # Kinder, friendlier no-cache for resources in dev
            response['Cache-control'] = 'no-cache'

        return response
