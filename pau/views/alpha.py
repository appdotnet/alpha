import logging
from django.conf import settings
import simplejson as json

from django.http import (Http404, HttpResponsePermanentRedirect, HttpResponseRedirect,
                         HttpResponse, HttpResponseNotAllowed, HttpResponseBadRequest)

from paucore.stats.statsd_client import timer
from paucore.utils.htmlgen import render_etree_to_string
from paucore.utils.python import cast_int
from paucore.utils.string import truncate
from paucore.utils.web import smart_reverse

from pau import bridge

from pau.presenters.feed import (FeedInteractionPresenter, ChooseFeedPostPresenter, PhotoPostPresenter,
                                 StarFacepilePresenter, build_tree_from_text_entity_pack, FeedBackfillButtonPresenter,
                                 FeedPostPresenter)
from pau.presenters.user import UserFollowPresenter, FollowButtonPresenter
from pau.utils.annotations import get_photo_annotations, get_attachment_annotations
from pau.utils.urls import oembed_url
from pau.views.base import PauMMLActionView
from pau.presenters.messages import PostCreatePresenter


logger = logging.getLogger('pau')


class PauStreamBaseView(PauMMLActionView):

    stream_function = None
    post_create_pre_text = ''
    presenter = ChooseFeedPostPresenter
    skip_presenter = FeedBackfillButtonPresenter
    stream_marker_view = False
    stream_marker_name = None
    show_new_post_box = True
    include_mobile_nav_btn = True

    def get_stream_object(self, request, *args, **kwargs):
        return None

    @property
    def presenter_kwargs(self,):
        return {
            'show_stream_marker': self.stream_marker_view,
        }

    def get_response_from_obj(self, request, obj):
        if obj is None:
            response = self.stream_function(request)
        else:
            response = self.stream_function(request, obj)
        return response

    def get_presenter_for_item(self, request, item):
        return self.presenter.from_item(request, item, **self.presenter_kwargs)

    def populate_stream_marker_context(self, request, response):
        """
        take the original response from the API (bridge) and concatenate some post-marker items to it
        """
        initial_min_id = response.meta.get('min_id')
        marker_id = int(response.meta.marker.id)
        items = list(response.data)
        self.view_ctx['__js_stream_marker_post_id'] = marker_id
        if initial_min_id and marker_id < int(initial_min_id):
            # our earliest item comes after the stream marker, so there are unread items we wouldn't display
            # so in this branch, we get some pre-marker items to display as well
            params = request.GET.copy()
            params.update({
                'before_id': marker_id + 1,
            })
            request.GET = params
            items.append('skip')
            stream_marker_response = self.get_response_from_obj(request, None)
            items.extend(stream_marker_response.data)
            # for pagination
            self.view_ctx['more'] = 'true' if stream_marker_response.meta['more'] else 'false'
            if hasattr(stream_marker_response.meta, 'min_id'):
                self.view_ctx['before_id'] = stream_marker_response.meta.min_id

        self.view_ctx['used_stream_marker'] = True

        item_presenters = []
        for item in items:
            if item == 'skip':
                item_presenters.append(self.skip_presenter.from_response(request, initial_min_id, marker_id))
            else:
                item_presenters.append(self.get_presenter_for_item(request, item))

        self.view_ctx['item_presenters'] = item_presenters

    def populate_stream_presenters(self, request, response, use_stream_marker=False):
        if use_stream_marker:
            self.populate_stream_marker_context(request, response)
        else:
            item_presenters = [self.get_presenter_for_item(request, item) for item in response.data]
            self.view_ctx['item_presenters'] = item_presenters

    def populate_stream_context(self, request, *args, **kwargs):
        obj = self.get_stream_object(request, *args, **kwargs)

        response = self.get_response_from_obj(request, obj)

        self.view_ctx.response_meta = response.meta

        use_stream_marker = False
        if request.user.is_authenticated() and self.stream_marker_view:
            use_stream_marker = (hasattr(response.meta, 'marker') and
                                 hasattr(response.meta.marker, 'id') and
                                 request.user.preferences.use_stream_markers and
                                 bool(cast_int(request.GET.get('backfill'), 1)))
            self.view_ctx['__js_page_load_hooks'] += ['init_stream_marker']

        self.view_ctx['more'] = 'true' if response.meta.get('more') else 'false'
        if hasattr(response.meta, 'max_id'):
            self.view_ctx['since_id'] = response.meta.max_id
        if hasattr(response.meta, 'min_id'):
            self.view_ctx['before_id'] = response.meta.min_id

        self.populate_stream_presenters(request, response, use_stream_marker=use_stream_marker)

    def populate_context(self, request, *args, **kwargs):
        super(PauStreamBaseView, self).populate_context(request, *args, **kwargs)
        self.populate_stream_context(request, *args, **kwargs)
        self.view_ctx['__js_page_load_hooks'] += ['init_stream', 'post_create.init_post_file_uploader']
        if request.user.is_authenticated():
            self.view_ctx['__js_viewer_username'] = request.user.username
        self.view_ctx['infinite_scroll'] = True
        post_create_pre_text = self.post_create_pre_text + ' ' if self.post_create_pre_text else ''
        if self.stream_marker_view:
            self.view_ctx['__js_stream_marker_name'] = self.stream_marker_name

        self.view_ctx['__js_permit_attachments'] = True
        self.view_ctx['show_new_post_box'] = self.show_new_post_box
        self.view_ctx['post_box_presenter'] = PostCreatePresenter.from_data(request, post_create_pre_text=post_create_pre_text)
        self.view_ctx['__js_additional_stream_view_params'] = self.view_ctx.get('__js_additional_stream_view_params', {})
        for arg in ('post_presenter', 'max_width', 'max_height'):
            arg_value = request.GET.get(arg)
            if arg_value:
                self.view_ctx['__js_additional_stream_view_params'][arg] = arg_value


class PauGlobalView(PauStreamBaseView):

    template_name = 'pau/global.html'
    page_title = 'Global Feed - App.net'
    page_description = 'The Global Feed on App.net'
    selected_nav_page = 'global'
    requires_auth = True

    def populate_context(self, request, *args, **kwargs):
        super(PauGlobalView, self).populate_context(request, *args, **kwargs)
        self.view_ctx.update_ctx({
            '__js_page_load_hooks': ['post_create.init'],
            '__js_insert_post_client_side': True
        })

global_stream = PauGlobalView.as_view(stream_function=bridge.global_stream)


class PauExploreStreamView(PauStreamBaseView):

    template_name = 'pau/explore.html'
    requires_auth = True

    def get_stream_object(self, request, explore_slug, *args, **kwargs):
        self.view_ctx['current_slug'] = explore_slug
        return explore_slug

    def populate_context(self, request, *args, **kwargs):
        super(PauExploreStreamView, self).populate_context(request, *args, **kwargs)
        self.view_ctx['explore_title'] = self.view_ctx.response_meta.get('explore_stream', {}).get('title') or 'Discover Posts'
        self.view_ctx['page_title'] = '%s - App.net' % self.view_ctx['explore_title']
        self.view_ctx['page_description'] = self.view_ctx.response_meta.get('explore_stream', {}).get('description') or 'Discover interesting posts on App.net'
        self.view_ctx.update_ctx({
            '__js_page_load_hooks': ['post_create.init']
        })

explore_stream = PauExploreStreamView.as_view(stream_function=bridge.explore_stream)


class PauStreamView(PauStreamBaseView):

    template_name = 'pau/user/stream.html'
    page_title = 'Your Stream - App.net'
    page_description = 'My stream'
    selected_nav_page = 'stream'
    stream_marker_view = True

    @property
    def stream_marker_name(self):
        return self.view_ctx.stream_marker_name

    def get_stream_object(self, request, *args, **kwargs):
        return request.user.adn_user

    def populate_context(self, request, *args, **kwargs):
        self.view_ctx.stream_marker_name = 'my_stream'
        if request.user.preferences.show_unified_in_pau:
            self.view_ctx.stream_marker_name = 'unified'

        super(PauStreamView, self).populate_context(request, *args, **kwargs)
        self.view_ctx['__js_insert_post_client_side'] = True
        self.view_ctx.update_ctx({
            '__js_page_load_hooks': ['post_create.init']
        })

user_stream = PauStreamView.as_view(stream_function=bridge.user_stream)


class PauInteractionsView(PauStreamBaseView):

    template_name = 'pau/user/interactions.html'
    page_title = 'Interactions - App.net'
    page_description = 'Interactions'
    presenter = FeedInteractionPresenter
    show_new_post_box = False
    selected_nav_page = 'interactions'


interactions = PauInteractionsView.as_view(stream_function=bridge.user_interactions_stream)


class PauMentionsView(PauStreamBaseView):

    template_name = 'pau/user/mentions.html'
    page_title = 'Mentions - App.net'
    page_description = 'My Mentions on App.net'
    selected_nav_page = 'mentions'

    def get_stream_object(self, request, *args, **kwargs):
        return request.user.adn_user

    def populate_context(self, request, *args, **kwargs):
        super(PauMentionsView, self).populate_context(request, *args, **kwargs)
        self.view_ctx['__js_insert_post_client_side_based_on_entity'] = {
            'type': 'mentions',
            'name': request.user.username
        }
        self.view_ctx.update_ctx({
            '__js_page_load_hooks': ['post_create.init']
        })


mentions = PauMentionsView.as_view(stream_function=bridge.mentions_stream)


class PauStarsFromUserView(PauStreamBaseView):

    template_name = 'pau/user/starred.html'
    page_title = 'Starred - App.net'
    page_description = "Posts I've Starred on App.net"
    selected_nav_page = None
    requires_auth = False
    selected_nav_page = 'stars'

    def get_stream_object(self, request, *args, **kwargs):
        owner_username = kwargs.get('username', '')
        owner = bridge.get_user_by_username(request, owner_username)
        self.view_ctx['owner'] = owner
        return owner

    def populate_context(self, request, *args, **kwargs):
        super(PauStarsFromUserView, self).populate_context(request, *args, **kwargs)
        self.view_ctx.update_ctx({
            '__js_page_load_hooks': ['post_create.init']
        })

stars_from_user = PauStarsFromUserView.as_view(stream_function=bridge.get_stars_for_user)


class PauStarredByView(PauStreamBaseView):
    requires_auth = False
    presenter = UserFollowPresenter
    show_new_post_box = False
    requires_auth = False
    template_name = 'pau/post/starred_by.html'
    page_title = 'Starred by - App.net'

    def get_stream_object(self, request, *args, **kwargs):
        post_id = kwargs.get('post_id', '')
        if not post_id:
            raise Http404()
        return post_id

    def populate_context(self, request, *args, **kwargs):
        super(PauStarredByView, self).populate_context(request, *args, **kwargs)

        self.view_ctx.update_ctx({
            '__js_page_load_hooks': ['post_create.init', 'init_follow']
        })

starred_by = PauStarredByView.as_view(stream_function=bridge.get_stars_for_post)


class PauRepostersView(PauStreamBaseView):
    requires_auth = False
    presenter = UserFollowPresenter
    show_new_post_box = False
    requires_auth = False
    template_name = 'pau/post/reposters.html'
    page_title = 'Reposted by - App.net'

    def get_stream_object(self, request, *args, **kwargs):
        post_id = kwargs.get('post_id', '')
        if not post_id:
            raise Http404()
        return post_id

    def populate_context(self, request, *args, **kwargs):
        super(PauRepostersView, self).populate_context(request, *args, **kwargs)

        self.view_ctx.update_ctx({
            '__js_page_load_hooks': ['post_create.init', 'init_follow']
        })

reposters = PauRepostersView.as_view(stream_function=bridge.get_reposters)


class PauFollowsBaseView(PauStreamBaseView):
    requires_auth = False
    presenter = UserFollowPresenter
    show_new_post_box = False
    template_name = 'pau/user/follows.html'

    def get_stream_object(self, request, *args, **kwargs):
        owner_username = kwargs.get('username', '')
        owner = bridge.get_user_by_username(request, owner_username)
        self.view_ctx['owner'] = owner
        return owner

    def populate_context(self, request, *args, **kwargs):
        super(PauFollowsBaseView, self).populate_context(request, *args, **kwargs)

        self.view_ctx.update_ctx({
            '__js_page_load_hooks': ['init_follow']
        })


class PauFollowsToView(PauFollowsBaseView):

    def populate_context(self, request, *args, **kwargs):
        super(PauFollowsToView, self).populate_context(request, *args, **kwargs)
        self.view_ctx['follow_type'] = "follows_to"
        meta_description = u'%s\'s followers on App.net' % (self.view_ctx['owner'].username)
        self.view_ctx['page_title'] = meta_description
        self.view_ctx['page_description'] = meta_description

follows_to = PauFollowsToView.as_view(stream_function=bridge.get_followers)


class PauFollowsFromView(PauFollowsBaseView):

    def populate_context(self, request, *args, **kwargs):
        super(PauFollowsFromView, self).populate_context(request, *args, **kwargs)
        self.view_ctx['follow_type'] = "follows_from"
        meta_description = u'Users %s is following on App.net' % (self.view_ctx['owner'].username)
        self.view_ctx['page_title'] = meta_description
        self.view_ctx['page_description'] = meta_description

follows_from = PauFollowsFromView.as_view(stream_function=bridge.get_following)


class PauHashtagsView(PauStreamBaseView):

    template_name = 'pau/hashtags.html'
    selected_nav_page = None
    requires_auth = False

    def get_stream_object(self, request, hashtag, *args, **kwargs):
        self.view_ctx['hashtag'] = hashtag
        self.post_create_pre_text = u'#%s' % (hashtag)
        self.view_ctx['page_title'] = '#%s - App.net' % (hashtag)
        self.view_ctx['page_description'] = 'Posts about #%s' % (hashtag)
        self.view_ctx['rss_link'] = 'https://api.app.net/feed/posts/tagged/%s' % (hashtag)
        return hashtag

    def populate_context(self, request, hashtag, *args, **kwargs):
        super(PauHashtagsView, self).populate_context(request, hashtag, *args, **kwargs)
        self.view_ctx['__js_insert_post_client_side_based_on_entity'] = {
            'type': 'hashtags',
            'name': hashtag
        }
        self.view_ctx.update_ctx({
            '__js_page_load_hooks': ['post_create.init', 'init_follow']
        })

hashtags = PauHashtagsView.as_view(stream_function=bridge.hashtags_stream)


def user_name_for_title(name):
    if name:
        return ' (%s)' % name
    return ''


class PauUserDetailView(PauStreamBaseView):

    requires_auth = False
    template_name = 'pau/user/detail.html'
    selected_nav_page = None

    def update_context_for_owner(self, request, owner):
        self.view_ctx['username'] = owner.username

        self.view_ctx['avatar_image'] = owner['avatar_image']
        self.view_ctx['cover_image'] = owner['cover_image']

        self.view_ctx['cover_image_shown'] = True

        owner_description = build_tree_from_text_entity_pack(request, owner.get('description', {}))
        self.view_ctx['owner_description'] = owner_description
        self.view_ctx['owner'] = owner
        self.view_ctx['owner_name'] = owner.get('name', '')
        self.view_ctx['num_followers'] = owner['counts']['followers']
        self.view_ctx['num_following'] = owner['counts']['following']
        self.view_ctx['num_starred'] = owner['counts']['stars']
        self.view_ctx['verified_domain'] = owner.get('verified_domain')
        if self.view_ctx['verified_domain']:
            # Not sure how I want to build this link
            self.view_ctx['verified_domain_link'] = owner['verified_link']
            if self.view_ctx['verified_domain'].startswith('www.'):
                # for display purposes, don't show www. in alpha
                self.view_ctx['verified_domain'] = self.view_ctx['verified_domain'][4:]

    def get_stream_object(self, request, username, *args, **kwargs):
        user = bridge.get_user_by_username(request, username)
        if not user:
            raise Http404()
        self.view_ctx['owner'] = user
        if request.user.is_authenticated() and request.user.adn_user.id != user.id:
            self.post_create_pre_text = u'@%s' % (username)
        self.view_ctx['rss_link'] = 'https://api.app.net/feed/rss/users/%d/posts' % (user.id)
        return user

    def populate_context(self, request, *args, **kwargs):
        super(PauUserDetailView, self).populate_context(request, *args, **kwargs)

        # XXX: owner is set in the stream function which is wrong and needs to change
        owner = self.view_ctx['owner']

        self.update_context_for_owner(request, owner)

        # User detail specific context
        self.view_ctx['follow_btn'] = FollowButtonPresenter.from_user_api_obj(request, owner, show_for_unauthenticated=True)
        self.view_ctx['page_title'] = '%s%s on App.net' % (owner.get('name', ''), user_name_for_title(owner.username))
        self.view_ctx['page_description'] = '%s' % (owner.get('description', {}).get('text', 'A user on App.net'))
        if request.user.is_authenticated() and owner.id == request.user.adn_user.id:
            self.view_ctx['selected_nav_page'] = 'profile'
            self.view_ctx['__js_insert_post_client_side'] = True

        self.view_ctx['__js_page_load_hooks'] += ['post_create.init', 'init_follow', 'pau.init_block_user', 'pau.init_mute_user']

    def action_redirect_to_signup(self, request, *args, **kwargs):
        user_id = request.POST.get('user_id')
        if not user_id:
            raise Http404()

        extra_params = {
            'action': 'follow',
            'user_id': user_id,
        }

        request.session['next_blob'] = extra_params

        return HttpResponseRedirect(smart_reverse(request, 'login', url_params={'next': request.build_absolute_uri()}))

user_detail = PauUserDetailView.as_view(stream_function=bridge.user_posts)


class PauPostDetailView(PauMMLActionView):

    requires_auth = False
    template_name = 'pau/post/detail.html'
    include_mobile_nav_btn = True

    @timer('pau.post_detail.populate_context')
    def populate_context(self, request, *args, **kwargs):
        super(PauPostDetailView, self).populate_context(request, *args, **kwargs)
        post_id = kwargs.get('post_id')
        before_post_objs, target_post_api_obj, after_post_objs = bridge.get_conversation(request, post_id)

        if target_post_api_obj.user and kwargs.get('username') != target_post_api_obj.user.username:
            new_url = smart_reverse(request, 'post_detail_view', kwargs={'username': target_post_api_obj.user.username,
                                    'post_id': str(target_post_api_obj.id)})
            self.view_ctx.response = HttpResponsePermanentRedirect(new_url)
            return

        if target_post_api_obj.get('is_deleted') and target_post_api_obj.get('repost_of'):
            # Deleted reposts should actually go away, so this can 404. If a user got deleted, their reposts may be ghosts
            # instead of being deleted correctly
            raise Http404()

        if all((target_post_api_obj.get('is_deleted'), (target_post_api_obj.get('reply_to') is None),
                (target_post_api_obj.get('num_replies') == 0))):
            # render normally but 404 status code
            self.view_ctx.status_code = 404

        original_post = target_post_api_obj.get('repost_of')
        if original_post:
            # This is the post detail of a repost post, all activity should be redirected to the
            # original post.
            new_url = smart_reverse(request, 'post_detail_view', kwargs={'username': original_post.user.username,
                                    'post_id': str(original_post.id)})
            self.view_ctx.response = HttpResponsePermanentRedirect(new_url)
            return

        owner = target_post_api_obj.user
        owner_id = owner['id'] if owner else None
        viewer_is_author = request.user.is_authenticated() and owner_id == request.user.adn_user.id

        if owner:
            name = target_post_api_obj.user.get('name') or target_post_api_obj.user.username
            self.view_ctx['page_title'] = u'%s: %s on App.net' % (name, truncate(target_post_api_obj.get('text', ''), 50))
            self.view_ctx['post_create_pre_text'] = u'@%s ' % (target_post_api_obj['user']['username']) if not viewer_is_author else ''
            self.view_ctx['page_description'] = u'%s' % (truncate(target_post_api_obj.get('text', ''), 100))
        else:
            # user of root post was deleted
            self.view_ctx['page_title'] = u'App.net'
            self.view_ctx['post_create_pre_text'] = ''
            self.view_ctx['page_description'] = u'This App.net post has been deleted'

        self.view_ctx['oembed_url'] = oembed_url(request.build_absolute_uri())
        self.view_ctx['post_a'] = target_post_api_obj
        self.view_ctx['main_post_inner'] = ChooseFeedPostPresenter.from_item(request, target_post_api_obj, show_deleted=True, single_post=True, in_conversation=True)
        self.view_ctx['before_post_presenters'] = [
            ChooseFeedPostPresenter.from_item(request, post_api_obj, show_deleted=True, in_conversation=True) for post_api_obj in before_post_objs
        ]
        self.view_ctx['after_post_presenters'] = [
            ChooseFeedPostPresenter.from_item(request, post_api_obj, show_deleted=True, in_conversation=True) for post_api_obj in after_post_objs
        ]
        self.view_ctx['num_stars'] = target_post_api_obj.num_stars
        self.view_ctx['num_reposts'] = target_post_api_obj.num_reposts
        self.view_ctx['star_facepile_presenter'] = StarFacepilePresenter.from_data(request, target_post_api_obj)
        self.view_ctx['owner'] = owner
        self.view_ctx['num_replies'] = target_post_api_obj['num_replies']
        self.view_ctx['__js_refresh_on_post_create'] = '1'
        self.view_ctx['__js_permit_attachments'] = True
        if before_post_objs:
            self.view_ctx['__js_post_id'] = post_id
        self.view_ctx['__js_page_load_hooks'] += ['init_follow', 'zoom_to_post', 'post_create.init_post_file_uploader']
        if request.user.is_authenticated():
            self.view_ctx['__js_page_load_hooks'] += ['post_create.init', ]
            self.view_ctx['__js_viewer_username'] = request.user.username

        self.view_ctx['post_box_presenter'] = PostCreatePresenter.from_data(request, btn_action='Reply', reply_to=target_post_api_obj)

post_detail = PauPostDetailView.as_view()


# Does this post (still) exist, and does it belong to this username?
def verify_post(username, post):
    if post and username:
        return all([not post.get('is_deleted', False), post.get('user') and username == post.user.username])
    return False


class PauPhotoView(PauMMLActionView):
    template_name = 'pau/post/photo.html'
    page_title = 'Photo - App.net'
    requires_auth = False

    def populate_context(self, request, username=None, post_id=None, photo_id=None, *args, **kwargs):
        super(PauPhotoView, self).populate_context(request, *args, **kwargs)

        try:
            post_id = int(post_id)
            photo_id = int(photo_id)
        except:
            raise Http404()

        post_api_obj = bridge.get_post(request, post_id)
        if not verify_post(username, post_api_obj):
            raise Http404()

        photo_annotations = get_photo_annotations(post_api_obj.get('annotations', []))
        num_photos = len(photo_annotations)
        # N.B. photo_id is 1-based
        if photo_id < 1 or photo_id > num_photos:
            raise Http404()

        photo_annotation = photo_annotations[photo_id - 1]
        value = photo_annotation['value']
        width = value['width']
        height = value['height']
        url = value.get('url_secure', value['url'])

        next_photo_url = None
        prev_photo_url = None
        if photo_id > 1:
            prev_photo_url = smart_reverse(request, 'photo', args=[username, post_id, photo_id - 1])
        if photo_id < num_photos:
            next_photo_url = smart_reverse(request, 'photo', args=[username, post_id, photo_id + 1])

        post_presenter = PhotoPostPresenter.from_item(request, post_api_obj)
        self.view_ctx['page_title'] = u'App.net | %s photo: %s' % (post_api_obj.user.username, truncate(post_api_obj.get('text', ''), 50))
        self.view_ctx['page_description'] = truncate(post_api_obj.get('text', self.view_ctx['page_title']), 100)

        self.view_ctx.update_ctx({
            'image_url': url,
            'image_width': width,
            'image_height': height,
            'next_photo_url': next_photo_url,
            'prev_photo_url': prev_photo_url,
            'post_presenter': post_presenter,
            'post_url': smart_reverse(request, 'post_detail_view', args=[username, post_id]),
            'post_api_obj': post_api_obj,
            'oembed_url': oembed_url(request.build_absolute_uri()),
            '__js_page_load_hooks': ['photo.init']
        })

photo = PauPhotoView.as_view()


def attachment(request, username, post_id, attachment_id):
    try:
        post_id = int(post_id)
        attachment_id = int(attachment_id)
    except:
        raise Http404()

    post = bridge.get_post(request, post_id)
    if not verify_post(username, post):
        raise Http404()

    # get list of net.app.core.file_lists, flatten them
    attachments_lists = get_attachment_annotations(post.get('annotations'))
    attachments = [item for al in attachments_lists for item in al['value']['net.app.core.file_list']]
    if attachment_id < 1 or attachment_id > len(attachments):
        raise Http404()

    url = attachments[attachment_id - 1]['url']

    return HttpResponseRedirect(url)


class PauAuthorizedIndexView(PauStreamView):
    requires_auth = True

authorized_index = PauAuthorizedIndexView.as_view(stream_function=bridge.user_stream)


class PauSplashView(PauMMLActionView):
    template_name = 'pau/splash.html'
    page_title = 'Welcome to Alpha by App.net'
    page_description = "Alpha by App.net."
    requires_auth = False

    def populate_context(self, request, *args, **kwargs):
        super(PauSplashView, self).populate_context(request, *args, **kwargs)
        self.view_ctx['hide_footer'] = True

splash_page = PauSplashView.as_view()


def index_router(request, *args, **kwargs):
    if request.user.is_authenticated():
        return authorized_index(request, *args, **kwargs)
    else:
        return splash_page(request, *args, **kwargs)


def create_post(request):
    # A thin shim to render the appropriate html for pau after we create a post. Ideally, we'd just call the api directly from
    # js but then we'd have to figure out how to do client side rendering and templates from api objects in js. Instead, just use
    # the python presenters we currently have.
    if request.method != 'POST':
        return HttpResponseNotAllowed(('POST',))

    try:
        post = json.loads(request.body)
    except:
        return HttpResponseBadRequest('Malformed json')

    text = post.get('text')
    if text:
        # we can move this to the js if we want to
        post['entities'] = {
            'links': [],
            'parse_links': True,
            'parse_markdown_links': True,
        }

    # call directly into bridge.call_api so we can mostly just pass the api reponse back through to the js without worrying about
    # parsing and formats of APIPost etc
    try:
        response_json = bridge.api.call_api(request, '/posts/', data=post, method='POST')
    except bridge.AlphaAPIException, e:
        return HttpResponse(json.dumps(e.response), content_type='application/json', status=e.response.meta.code)

    post_a = bridge.APIPost.from_response_data(response_json.data)

    presenter = FeedPostPresenter.from_item(request, post_a)
    response_json.data['html'] = render_etree_to_string(presenter.generate_html())

    return HttpResponse(json.dumps(response_json), content_type='application/json')


def well_known_webfinger(request):
    resource = request.GET.get('resource')
    if not resource:
        raise Http404()

    fake_email = resource.lower().replace('acct:', '')
    username, domain = fake_email.split('@', 1)

    current_domain = 'alpha.%s' % (settings.PARENT_HOST)
    if domain != current_domain:
        raise Http404()

    user = bridge.get_user_by_username(request, username)

    if not user:
        raise Http404()

    def link(rel, href, _type=None):
        link = dict(rel=rel, href=href)
        if _type:
            link['type'] = _type

        return link

    user_profile = smart_reverse(request, 'user_detail_view', args=[username], force_qualified=True)
    activitystream = 'https://api.%s/users/@%s/activitystream' % (settings.PARENT_HOST, username)
    resp = json.dumps({
        "subject": 'acct:%s@%s' % (username, current_domain),
        "aliases": [
            user_profile,
        ],
        "links": [
            link(rel='http://webfinger.net/rel/profile-page', href=user_profile, _type='text/html'),
            link(rel='http://activitystrea.ms/specs/json/1.0/', href=activitystream)
        ]
    })

    return HttpResponse(resp, content_type='application/json')
