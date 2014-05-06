from django.conf import settings

def oembed_url(url):
    return "%s/oembed?url=%s" % (settings.PUBLIC_API_ROOT, url)
