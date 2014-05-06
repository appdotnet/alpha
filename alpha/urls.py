from django.conf import settings
from django.conf.urls import *

from pau.constants import USERNAME_RE, explore_slug_url_regex

user_patterns = patterns(
    '',
    # Because user detail has an optional trailing slash, it is below.
    url(r'^post/(?P<post_id>\d+)$', 'pau.views.alpha.post_detail', name='post_detail_view'),
    url(r'^post/(?P<post_id>\d+)/stars/$', 'pau.views.alpha.starred_by', name='starred_by'),
    url(r'^post/(?P<post_id>\d+)/reposters/$', 'pau.views.alpha.reposters', name='reposters'),
    url(r'^post/(?P<post_id>\d+)/photo/(?P<photo_id>\d+)$', 'pau.views.alpha.photo', name='photo'),
    url(r'^post/(?P<post_id>\d+)/attachment/(?P<attachment_id>\d+)$', 'pau.views.alpha.attachment', name='attachment'),
    url(r'^followers/$', 'pau.views.alpha.follows_to', name='follows_to'),
    url(r'^following/$', 'pau.views.alpha.follows_from', name='follows_from'),
    url(r'^stars/$', 'pau.views.alpha.stars_from_user', name='stars_from_user'),
)

urlpatterns = patterns(
    '',
    url(r'^$', 'pau.views.alpha.index_router', name='home'),

    # oauth/access_token is a POST endpoint so we can't just redirect it
    # url(r'^oauth/access_token$', 'moku.views.auth.access_token', name='access_token'),

    # social auth
    url(r'^login/$', 'social.apps.django_app.views.auth', {'backend': 'appdotnet'}, name='login'),
    url(r'^logout/$', 'pau.views.auth.logout', name='logout'),
    url(r'^complete/(?P<backend>[^/]+)/$', 'pau.views.auth.complete', name='complete'),
    # I'd like to kill this since I'm mostly overriding what I want but it wants this to url resolve things like social:complete
    url('', include('social.apps.django_app.urls', namespace='social')),

    # alpha URLs
    url(r'^global/$', 'pau.views.alpha.global_stream', name='global'),

    url(r'^omo-api-proxy/posts$', 'pau.views.alpha.create_post'),
    url(r'^omo-api-proxy/(?P<path>.+)?$', 'pau.views.proxy.ajax_api_proxy', name='omo_api_proxy'),
    url(r'^mentions/$', 'pau.views.alpha.mentions', name='mentions'),
    url(r'^interactions/$', 'pau.views.alpha.interactions', name='interactions'),
    url(r'^browse/%s/$' % explore_slug_url_regex, 'pau.views.alpha.explore_stream', name='explore'),
    url(r'^hashtags/(?P<hashtag>.+)$', 'pau.views.alpha.hashtags', name='hashtags'),

    url(r'^\.well-known/webfinger$', 'pau.views.alpha.well_known_webfinger'),
    # Because the trailing slash on user detail is optional, I'm special-casing this. But
    # otherwise, we can stop c/p'ing the username regular expression below.
    # Add views that should be under usernames to user_patterns above.
    url(r'^(?P<username>%s)/?$' % (USERNAME_RE), 'pau.views.alpha.user_detail', name='user_detail_view'),
    url(r'^(?P<username>%s)/' % (USERNAME_RE), include(user_patterns)),
)

if settings.DEBUG:
    urlpatterns += patterns(
        '',
        (r'^pau-static/(?P<path>.*)$', 'django.contrib.staticfiles.views.serve'),
        (r'^static/pau/(?P<path>.*)$', 'django.contrib.staticfiles.views.serve'),
    )
