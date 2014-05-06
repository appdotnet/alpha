import collections
import logging
import simplejson as json
from iso8601 import parse_date

import adnpy

from django.core.exceptions import PermissionDenied
from django.http import Http404

from paucore.stats.statsd_client import timer
from paucore.utils.data import extract_id, is_seq_not_string
from paucore.utils.web import append_query_string, smart_reverse

logger = logging.getLogger(__name__)


def annotations_to_dict(annotations):
    annotations_by_key = collections.defaultdict(list)
    if annotations:
        for annotation in annotations:
            annotations_by_key[annotation.type].append(annotation.get('value', {}))
    return annotations_by_key


def get_annotation_by_key(annotations_by_key, key, result_format='list'):
    value = annotations_by_key.get(key)
    if not value:
        return value

    if result_format == 'one':
        return value[0]

    return value


class BridgeJSON(dict):
    def __setattr__(self, name, val):
        return self.__setitem__(name, val)

    def __getattr__(self, name):
        try:
            return self.__getitem__(name)
        except KeyError:
            raise AttributeError(name)

    def __init__(self, data=None):
        super(BridgeJSON, self).__init__()
        if not data:
            return

        for k, v in data.iteritems():
            if isinstance(v, collections.Mapping):
                self[k] = BridgeJSON(v)
            elif v and is_seq_not_string(v) and isinstance(v[0], collections.Mapping):
                self[k] = [BridgeJSON(i) for i in v]
            else:
                self[k] = v

    @classmethod
    def from_string(cls, raw_json):
        return cls(json.loads(raw_json))


class APIModel(BridgeJSON):
    @classmethod
    def from_response_data(cls, data):
        model = cls(data)
        model.annotations_by_key = annotations_to_dict(model.get('annotations'))

        return model

    def get_annotation(self, key, result_format='list'):
        return get_annotation_by_key(self.get('annotations_by_key', {}), key, result_format=result_format)


class APIUser(APIModel):
    @classmethod
    def from_response_data(cls, data):
        user = super(APIUser, cls).from_response_data(data)
        user.avatar_image['30s'] = append_query_string(user.avatar_image.url, params={'w': 30, 'h': 30})
        user.avatar_image['57s'] = append_query_string(user.avatar_image.url, params={'w': 57, 'h': 57})
        user.avatar_image['80s'] = append_query_string(user.avatar_image.url, params={'w': 80, 'h': 80})
        user.cover_image['720r'] = append_query_string(user.cover_image.url, params={'w': 720})
        user.cover_image['862r'] = append_query_string(user.cover_image.url, params={'w': 862})
        user.id = int(user.id)
        # XXX: We need to change our code at some point to handle datetimes with a timezone
        user.created_at = parse_date(user.created_at).replace(tzinfo=None)
        if 'name' not in user:
            user.name = ''

        return user


class APIPost(APIModel):
    @classmethod
    def from_response_data(cls, data):
        post = super(APIPost, cls).from_response_data(data)
        post.id = int(post.id)
        if 'user' in post:
            post.user = APIUser.from_response_data(post.user)
        else:
            post.user = None
        post.starred_by = [APIUser.from_response_data(u) for u in post.get('starred_by', [])]
        post.reposters = [APIUser.from_response_data(u) for u in post.get('reposters', [])]
        # XXX: We need to change our code at some point to handle datetimes with a timezone
        post.created_at = parse_date(post.created_at).replace(tzinfo=None)

        # If there is a repost object setup the avatar assets for it as well
        repost_of = post.get('repost_of')
        if repost_of:
            post.repost_of = APIPost.from_response_data(post.repost_of)

        return post


class APIChannel(APIModel):
    @classmethod
    def from_response_data(cls, data):
        channel = super(APIChannel, cls).from_response_data(data)
        if 'owner' in channel:
            channel.owner = APIUser.from_response_data(channel.owner)
        else:
            channel.owner = None

        if channel.type == 'net.app.core.broadcast':
            channel = attach_metadata_to_channel(channel)

        return channel


class APIInteraction(APIModel):
    action_mapping = {
        'follow': APIUser,
        'star': APIPost,
        'reply': APIPost,
        'repost': APIPost,
        'broadcast_create': APIChannel,
        'broadcast_subscribe': APIChannel,
        'broadcast_unsubscribe': APIChannel,
    }
    # This is kind of duplicated with FeedInteractionPresenter.allowed_actions right now.
    allowed_interactions = action_mapping.keys() + ['welcome']

    @classmethod
    def from_response_data(cls, data):
        interaction = super(APIInteraction, cls).from_response_data(data)

        api_model = cls.action_mapping.get(interaction.action)
        if api_model:
            interaction.objects = map(api_model.from_response_data, interaction.objects)
        interaction.users = map(APIUser.from_response_data, interaction.users)
        # XXX: We need to change our code at some point to handle datetimes with a timezone
        interaction.event_date = parse_date(interaction.event_date).replace(tzinfo=None)
        return interaction


class AlphaAPIException(Exception):
    def __init__(self, api_response):
        super(AlphaAPIException, self).__init__(api_response.meta.error_message)
        self.response = api_response
        self.error_id = api_response.meta.get('error_id')
        self.error_slug = api_response.meta.get('error_slug')

    def __repr__(self):
        return "%s error_id: %s error_slug: %s" % (super(AlphaAPIException, self).__repr__(), self.error_id, self.error_slug)


class AlphaBadRequestAPIException(AlphaAPIException):
    def __init__(self, api_response):
        api_response.meta.error_message = api_response.meta.error_message.replace('Bad Request: ', '')
        super(AlphaBadRequestAPIException, self).__init__(api_response)


class AlphaAuthAPIException(AlphaAPIException):
    pass


class AlphaRateLimitAPIException(AlphaAPIException):
    pass


class AlphaInsufficientStorageException(AlphaAPIException):
    pass


def api_extract_id(obj):
    "Allows a method to take either a id, an APIModel, or a real model"

    if isinstance(obj, APIModel):
        return obj.get('id')
    else:
        return extract_id(obj)


class AlphaAPI(object):
    # keep this in sync with the LazyApi middleware
    migrations = set()
    allow_http = True

    def __init__(self, user=None, app=None, scopes=None):
        self.enabled_migrations = '&'.join('%s=1' % m for m in self.migrations)
        self.access_token = None

    def call_api(self, request, path, params=None, data=None, method='GET', post_type='json', headers=None):
        headers = headers or {}
        api_params = {
            'include_annotations': '1',
            'include_delete': '0'
        }

        api_params.update(request.GET)
        if params:
            api_params.update(params)

        api_method = request.omo_api.request
        if data and method in ('POST', 'PUT'):
            if post_type == 'json':
                # adnpy will json.dumps in this case
                api_method = request.omo_api.request_json
            else:
                data = json.dumps(data)

        # TODO remove all the alpha specific exceptions and just use the adnpy ones
        try:
            response = api_method(method, path, params=api_params, data=data, headers=headers)
        except adnpy.errors.AdnBadRequestAPIException, e:
            # 400
            raise AlphaBadRequestAPIException(e.response)
        except adnpy.errors.AdnAuthAPIException, e:
            # 401
            raise AlphaAuthAPIException(e.response)
        except adnpy.errors.AdnPermissionDenied:
            # 403
            raise PermissionDenied()
        except adnpy.errors.AdnMissing:
            # 404
            raise Http404()
        except adnpy.errors.AdnRateLimitAPIException, e:
            # 429
            raise AlphaRateLimitAPIException(e.response)
        except adnpy.errors.AdnInsufficientStorageException, e:
            # 507
            raise AlphaInsufficientStorageException(e.response)
        except adnpy.errors.AdnAPIException, e:
            # anything else not 200
            raise AlphaAPIException(e.response)

        # return the exact same format as old_call_api
        return BridgeJSON(response.serialize())

    def get_posts(self, request, path, *args, **kwargs):
        response = self.call_api(request, path, *args, **kwargs)
        response.data = [APIPost.from_response_data(post) for post in response.data]
        return response

    def get_users(self, request, path, *args, **kwargs):
        response = self.call_api(request, path, *args, **kwargs)
        response.data = [APIUser.from_response_data(post) for post in response.data]
        return response

    def posts_stream_global(self, request, *args, **kwargs):
        return self.get_posts(request, '/posts/stream/global', *args, **kwargs)

    def posts_stream_explore(self, request, slug, *args, **kwargs):
        return self.get_posts(request, '/posts/stream/explore/%s' % slug, *args, **kwargs)

    def list_explore_streams(self, request, *args, **kwargs):
        return self.call_api(request, '/posts/stream/explore', *args, **kwargs)

    def posts_stream(self, request, *args, **kwargs):
        return self.get_posts(request, '/posts/stream/', *args, **kwargs)

    def posts_stream_unified(self, request, *args, **kwargs):
        return self.get_posts(request, '/posts/stream/unified', *args, **kwargs)

    def posts_tag(self, request, tag, *args, **kwargs):
        return self.get_posts(request, '/posts/tag/%s' % tag, *args, **kwargs)

    def post_stars(self, request, post, *args, **kwargs):
        post_id = api_extract_id(post)
        return self.get_users(request, '/posts/%s/stars' % post_id, *args, **kwargs)

    def post_reposts(self, request, post, *args, **kwargs):
        post_id = api_extract_id(post)
        return self.get_users(request, '/posts/%s/reposters' % post_id, *args, **kwargs)

    def get_post(self, request, post, *args, **kwargs):
        post_id = api_extract_id(post)
        response = self.call_api(request, '/posts/%s' % post_id, *args, **kwargs)
        response.data = APIPost.from_response_data(response.data)
        return response

    def get_thread(self, request, post, *args, **kwargs):
        post_id = api_extract_id(post)
        return self.get_posts(request, '/posts/%s/replies' % post_id, *args, **kwargs)

    def users_mentions(self, request, user, *args, **kwargs):
        user_id = api_extract_id(user)
        return self.get_posts(request, '/users/%s/mentions' % user_id, *args, **kwargs)

    def users_stars(self, request, user, *args, **kwargs):
        user_id = api_extract_id(user)
        return self.get_posts(request, '/users/%s/stars' % user_id, *args, **kwargs)

    def users_posts(self, request, user, *args, **kwargs):
        user_id = api_extract_id(user)
        return self.get_posts(request, '/users/%s/posts' % user_id, *args, **kwargs)

    def user_followers(self, request, user, *args, **kwargs):
        user_id = api_extract_id(user)
        return self.get_users(request, '/users/%s/followers' % user_id, *args, **kwargs)

    def user_following(self, request, user, *args, **kwargs):
        user_id = api_extract_id(user)
        return self.get_users(request, '/users/%s/following' % user_id, *args, **kwargs)

    def interactions(self, request, *args, **kwargs):
        kwargs.setdefault('params', {})
        allowed_interactions = APIInteraction.allowed_interactions
        kwargs['params'].setdefault('interaction_actions', ','.join(allowed_interactions))

        response = self.call_api(request, '/users/me/interactions', *args, **kwargs)
        response.data = filter(None, [APIInteraction.from_response_data(interaction) for interaction in response.data])
        return response

    def get_user(self, request, user, *args, **kwargs):
        user_id = api_extract_id(user)
        response = self.call_api(request, '/users/%s' % user_id, *args, **kwargs)
        response.data = APIUser.from_response_data(response.data)
        return response

    def follow(self, request, target_user, *args, **kwargs):
        target_id = api_extract_id(target_user)
        response = self.call_api(request, '/users/%s/follow' % target_id, method='POST', *args, **kwargs)
        response.data = APIUser.from_response_data(response.data)
        return response

    class Stream(object):
        """Inspired by tweepy.cursor.Cursor"""

        def __init__(self, api_method, *args, **kwargs):
            self.api_method = api_method
            self.args = args
            kwargs.setdefault('params', {})
            self.kwargs = kwargs
            self.min_id = None
            self.max_id = None
            self.has_more = None

        def next(self):
            if self.has_more is False:
                raise StopIteration
            self.kwargs['params']['before_id'] = self.min_id
            response = self.api_method(*self.args, **self.kwargs)

            self.min_id = response.meta.get('min_id')
            self.max_id = response.meta.get('min_id')
            self.has_more = response.meta.get('more', False)  # once we've made a request don't set it to None again
            if not response.data:
                raise StopIteration
            return response

        def __iter__(self):
            return self

api = AlphaAPI()


@timer('omo.bridge.get_conversation')
def get_conversation(request, post_id):

    post_id = int(post_id)
    params = {
        'include_starred_by': '1',
        'include_deleted': '1',
        'count': 200
    }
    rounds = 0

    # what we're returning
    before = []
    target = None
    after = []

    for post_chunk in api.Stream(api.get_thread, request, post_id, params=params):
        rounds += 1

        if rounds > 8:
            before = after = []
            if target is None:
                resp = api.get_post(request, post_id)
                target = resp.data
            break

        for p in post_chunk.data:
            if p.id < post_id:
                before.insert(0, p)
            elif p.id == post_id:
                target = p
            else:
                after.insert(0, p)
    if not target:
        raise Http404()

    return before, target, after


def get_post(request, post_id):
    post = api.get_post(request, post_id).data
    if post.machine_only:
        return None
    return post


def global_stream(request):
    return api.posts_stream_global(request)


def explore_stream(request, explore_slug):
    try:
        resp = api.posts_stream_explore(request, explore_slug)
    except AlphaAPIException, e:
        if e.response.meta.code == 404:
            raise Http404()
        else:
            raise
    return resp


def list_explore_streams(request):

    def adjust_url(stream):
        stream['url'] = smart_reverse(request, 'explore', args=[stream['slug']])
        return stream

    return map(adjust_url, api.list_explore_streams(request).data)


def user_stream(request, *args, **kwargs):
    params = {}
    if request.user.preferences.disable_leading_mentions_filter:
        params['include_directed_posts'] = 1

    if request.user.preferences.show_unified_in_pau:
        return api.posts_stream_unified(request, params=params)
    else:
        return api.posts_stream(request, params=params)


def user_posts(request, user):
    return api.users_posts(request, user)


def mentions_stream(request, user):
    return api.users_mentions(request, user)


def get_stars_for_user(request, user):
    return api.users_stars(request, user)


def hashtags_stream(request, hashtag):
    return api.posts_tag(request, hashtag)


def user_interactions_stream(request):
    return api.interactions(request)


def get_stars_for_post(request, post):
    return api.post_stars(request, post)


def get_reposters(request, post):
    return api.post_reposts(request, post)


def get_followers(request, user):
    return api.user_followers(request, user)


def get_following(request, user):
    return api.user_following(request, user)


def get_user_by_username(request, username):
    return api.get_user(request, '@%s' % username).data


def follow(request, target_user):
    return api.follow(request, target_user)


def attach_metadata_to_channel(channel):
    channel.title = 'Channel %s' % (channel.id)
    channel.description = ''
    channel.tags = []
    channel.id = int(channel.id)

    metadata = channel.get_annotation('net.app.core.broadcast.metadata', result_format='one')
    if metadata:
        channel.title = metadata.get('title', channel.title)
        channel.description = metadata.get('description', channel.description)
        channel.tags = metadata.get('tags', channel.tags)

    fallback_url = channel.get_annotation('net.app.core.fallback_url', result_format='one')
    if fallback_url:
        channel.canonical_url = fallback_url.get('url')

    return channel


# After discussion with Thurman this is DIAF method. Probably should live
# somewhere else, but that means bridge should probably live somewhere else as well
def handle_actions_blob(request, blob_dict):
    action = blob_dict.get('action')

    if action == 'follow':
        user_id = blob_dict.get('user_id')
        if not user_id:
            return

        try:
            api.follow(request, user_id)
        except AlphaBadRequestAPIException:
            pass

    return
