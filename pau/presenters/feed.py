import logging
import re
import pytz
from urlparse import urljoin, urlparse

from django.core.urlresolvers import NoReverseMatch

from paucore.utils.image import fit_to_box
from paucore.utils.date import naturaldate
from paucore.utils.data import intersperse
from paucore.utils.presenters import AbstractPresenter, html, html_list_to_english
from paucore.utils.web import smart_reverse, append_query_string

from pau.utils.annotations import get_photo_annotations, get_video_annotations, get_place_annotation

logger = logging.getLogger(__name__)


def build_tree_from_text_entity_pack(request, text_entity_pack, itemscope='https://join.app.net/schemas/Post', convert_new_lines=False):
    # adapted from omo models TextEntityPack.html
    def entity_text(e):
        return text_entity_pack['text'][e['pos']:e['pos'] + e['len']]

    mention_builder = lambda m: html.a(
        itemprop='mention',
        data={
            'mention-name': m['name'], 'mention-id': m['id']
        },
        href=smart_reverse(request, 'user_detail_view', args=[m['name']], force_qualified=True),
        *[entity_text(m)]
    )
    hashtag_builder = lambda h: html.a(
        itemprop='hashtag',
        data={
            'hashtag-name': h['name']
        },
        href=smart_reverse(request, 'hashtags', args=[h['name']], force_qualified=True),
        *[entity_text(h)]
    )
    link_builder = lambda l: html.a(href=l['url'], target="_blank", rel='nofollow', *[entity_text(l)])

    # map starting position, length of entity placeholder to the replacement html
    entity_map = {}
    for entity_key, builder in [('mentions', mention_builder), ('hashtags', hashtag_builder), ('links', link_builder)]:
        for entity in text_entity_pack.get('entities', {}).get(entity_key, []):
            try:
                entity_map[(entity['pos'], entity['len'])] = builder(entity)
            except NoReverseMatch:
                logger.warning('Could not build link for entity=%s in Pau path %s.', entity.get('name'), request.path)

    # replace strings with html
    html_pieces = []
    text_idx = 0  # our current place in the original text string
    for entity_start, entity_len in sorted(entity_map.keys()):
        if text_idx != entity_start:
            # if our current place isn't the start of an entity, bring in text until the next entity
            html_pieces.append(text_entity_pack.get('text', "")[text_idx:entity_start])

        # pull out the entity html
        entity_html = entity_map[(entity_start, entity_len)]
        html_pieces.append(entity_html)

        # move past the entity we just added
        text_idx = entity_start + entity_len

    # clean up any remaining text
    html_pieces.append(text_entity_pack.get('text', "")[text_idx:])
    if convert_new_lines:
        new_html_pieces = []
        for piece in html_pieces:
            if isinstance(piece, basestring) and '\n' in piece:
                new_html_pieces += list(intersperse(html.br(), piece.split('\n')))
            else:
                new_html_pieces.append(piece)

        html_pieces = new_html_pieces

    # TODO: link to schema
    return html.span(itemscope=itemscope, *html_pieces)


class FeedPostPresenter(AbstractPresenter):
    show_reply_button = True
    show_via_attribution = True
    show_star_button = True
    show_repost_button = True
    show_mute_button = True
    show_report_button = True
    show_delete_button = True
    hidden = False

    @classmethod
    def from_item(cls, request, post_a, show_deleted=False, single_post=False, show_stream_marker=False,
                  reply_link_format='to_self', in_conversation=False, click_data=None, *args, **kwargs):
        presenter = cls(*args, **kwargs)
        presenter.request = request
        presenter.post_a = post_a

        presenter.repost = None
        if hasattr(post_a, 'repost_of') and post_a.repost_of:
            presenter.repost = post_a
            # Render the original post not the repost
            presenter.post_a = post_a = post_a.repost_of
        if post_a.user:
            presenter.user_detail_url = smart_reverse(request, 'user_detail_view', args=[post_a.user.username])
            presenter.post_detail_url = smart_reverse(request, 'post_detail_view', kwargs={'username': post_a.user.username, 'post_id': str(post_a.id)})
        presenter.show_deleted = show_deleted
        presenter.single_post = single_post
        presenter.reply_link_format = reply_link_format
        presenter.in_conversation = in_conversation
        presenter.is_authenticated = request.user.is_authenticated()
        presenter.show_stream_marker = request.user.is_authenticated() and request.user.preferences.use_stream_markers and show_stream_marker
        presenter.click_data = click_data or {}
        return presenter

    def generate_html(self):
        if self.post_a.get('is_deleted') and not self.show_deleted:
            return ''

        post_data = {
            'post-id': self.post_a.id,
            # Should the post be remove from the page.
            # or should we insert [deleted] text
            'post-remove-from-page': '0' if self.show_deleted else '1'
        }

        if self.post_a.user:
            post_data['post-author-username'] = self.post_a.user.username
            post_data['post-author-id'] = self.post_a.user.id
        else:
            post_data['post-author-deleted'] = '1'

        if self.repost:
            post_data['post-parent-id'] = self.repost.id

        classes = ['post-container', 'subpixel']
        if not self.single_post and self.in_conversation:
            classes += ['p-in-reply-to', 'h-cite']
        else:
            classes += ['h-entry']

        if self.post_a.get('is_deleted'):
            classes.append('deleted')
        if self.hidden:
            classes.append('hide')

        avatar_size = 114
        avatar_classes = ['avatar']
        if self.single_post:
            classes.append('single-post-container')
            avatar_classes.append('large')
            avatar_size = 160

        avatar_block = ''
        if self.post_a.user:
            avatar_url = append_query_string(self.post_a.user.avatar_image.url, params={'w': avatar_size, 'h': avatar_size})
            avatar_block = html.div(class_='media', *[
                html.a(class_=avatar_classes, data=self.click_data, style={'background-image': 'url(%s)' % avatar_url},
                       href=self.user_detail_url)
            ])

        tree = html.div(class_=classes, data=post_data, name=str(self.post_a.id), *[
            html.div(class_='content', *[
                avatar_block,
                self.generate_post_header(),
                self.generate_post_body(),
                self.generate_post_footer()
            ]),
        ])
        return tree

    def generate_post_header(self):
        username_block = html.span(class_='username')

        if self.post_a.user:
            username_block = html.span(class_='username p-author h-card', *[
                html.a(href=self.user_detail_url, data=self.click_data, class_='p-nickname u-url', *[
                    self.post_a.user.username
                ])
            ])

        header_items = []

        # star this post
        if self.is_authenticated:
            if self.show_star_button:
                star_presenter = StarPresenter.from_data(self.request, self.post_a)
                star_html = star_presenter.generate_html()
                header_items.append(
                    html.li(class_='yui3-u', *[
                        star_html
                    ])
                )

            if self.show_repost_button:
                repost_button = RepostButtonPresenter.from_data(self.request, self.post_a)
                repost_button_html = repost_button.generate_html()
                if repost_button_html != '':
                    header_items.append(
                        html.li(class_='yui3-u repost', *[
                            repost_button_html
                        ])
                    )

        return html.div(class_='post-header', *[
            username_block,
            html.ul(class_='ul-horizontal unstyled yui3-u fixed-right ta-right', *header_items)
        ])
        return username_block

    def generate_media_block(self, default_size=100):
        # Make a thumbnail for the first photo or video
        media_block = ''
        link_kwargs = None
        photo_annotations = get_photo_annotations(self.post_a.get('annotations', []))
        video_annotations = get_video_annotations(self.post_a.get('annotations', []))

        if photo_annotations:
            icon_class = 'icon-zoom-in'
            value = photo_annotations[0]['value']

            link_kwargs = {
                'href': value.get('embeddable_url', smart_reverse(self.request, 'photo',
                                                                  args=[self.post_a.user.username, self.post_a.id, 1])),
            }

            # keep the :// here
            photos_domain = '://photos.app.net'
            if photos_domain not in link_kwargs['href']:
                link_kwargs['target'] = '_blank'
                link_kwargs['rel'] = 'nofollow'
            else:
                link_kwargs['data-pjax-url'] = smart_reverse(self.request, 'pau.views.alpha.photo', args=[self.post_a.user.username,
                                                             self.post_a.id, 1], force_qualified=True)
        elif video_annotations:
            icon_class = 'icon-play-circle'
            value = video_annotations[0]['value']
            embeddable_url = value.get('embeddable_url')
            if embeddable_url:
                link_kwargs = {
                    'href': embeddable_url,
                    'target': '_blank',
                    'rel': 'nofollow'
                }

        if link_kwargs:
            thumbnail_width = value['thumbnail_width']
            thumbnail_height = value['thumbnail_height']
            thumbnail_url = value.get('thumbnail_url_secure', value['thumbnail_url'])

            try:
                max_width = int(self.request.GET.get('max_width', default_size))
                max_height = int(self.request.GET.get('max_height', default_size))
            except:
                max_width = max_height = default_size

            include_zoom = bool(self.request.GET.get('include_zoom', True))
            display_width, display_height = map(str, fit_to_box(thumbnail_width, thumbnail_height, max_width, max_height))

            media_block = [
                html.div(class_='post-media', *[
                    html.a(class_="shadow-overlay", data=self.click_data, *[
                        html.i(class_=icon_class) if include_zoom else ''
                    ], **link_kwargs),
                    html.div(class_='inner-shadow-overlay'),
                    html.img(src=thumbnail_url, width=display_width, height=display_height)
                ])
            ]

        return media_block

    def generate_post_body_text(self):
        body_text = '[Post deleted]'
        if not self.post_a.get('is_deleted'):
            body_text = build_tree_from_text_entity_pack(self.request, self.post_a)

        text_block = html.div(class_='post-text', *[
            html.span(class_='post-content e-content', *[
                body_text,
            ])
        ])

        return text_block

    def generate_post_body(self):
        # Main post text
        text_block = self.generate_post_body_text()
        # media annotation, eg. oEmbed photos
        media_block = self.generate_media_block()

        if media_block:
            tree = html.div(class_='body has-media', *[
                html.div(class_='content', *[
                    html.div(class_='media', *media_block),
                    text_block,
                ])
            ])
        else:
            tree = html.div(class_='body', *[
                text_block,
            ])

        return tree

    def reply_button(self):
        href = '#' if self.reply_link_format == 'to_self' else self.post_detail_url
        data = {'reply-to': ''}
        data.update(self.click_data)
        tree = html.li(class_='show-on-hover yui3-u', *[
            html.a(href=href, data=data, *[
                html.i(class_='icon-share-alt'),
                " Reply"
            ])
        ])
        return tree

    def generate_post_footer(self):
        if self.post_a.get('is_deleted'):
            return ''

        footer_top_row = []
        # repost
        # N.B. if you change this html (reposts), make sure to change the ajax handler for repost,
        # which duplicates this html to provide client-side feedback
        viewer_has_reposted = self.post_a.get('you_reposted')
        if self.repost or viewer_has_reposted:
            # yes, there is a priority order of reposter info - viewer trumps everyone else
            if viewer_has_reposted:
                reposter_username = self.request.user.username
                reposter_display = 'you'
            elif self.repost:
                reposter_username = self.repost.user.username
                reposter_display = '@' + reposter_username
            footer_top_row.append(
                html.div(class_='post-reposted-by yui3-u', *[
                    html.span(class_='reposted-by-text', *[
                        html.i(class_='icon-repost'),
                        html.span(' Reposted by ', *[
                            html.a(href=smart_reverse(self.request, 'user_detail_view', args=[reposter_username]),
                                   data=self.click_data, *[reposter_display]),
                        ])
                    ])
                ])
            )

        # place
        place_annotation = get_place_annotation(self.post_a.get('annotations', []))
        if place_annotation:
            if place_annotation['value'].get('address'):
                place_pretty = u'%s \u2014 %s' % (place_annotation['value']['name'], place_annotation['value']['address'])
            else:
                place_pretty = u'%s' % place_annotation['value']['name']

            tags_html = []
            if place_annotation.get('type') == 'net.app.core.checkin':
                factual_url = urljoin('http://factual.com/', place_annotation['value']['factual_id'])
                tags_html.append(html.meta(name="factual", content=factual_url))
            tags_html.append(html.span(class_='posted-from-text', *[
                html.i(class_='icon-pushpin'),
                html.span(' at %s' % place_pretty),
            ]))
            footer_top_row.append(html.div(class_='post-posted-from-place yui3-u', *tags_html))
        footer_bottom_row = []

        # timestamp
        timezone_str = self.request.user.adn_user.timezone if self.is_authenticated else 'America/Los_Angeles'
        viewers_timezone = pytz.timezone(timezone_str)
        non_relative_timestamp = pytz.utc.localize(self.post_a.created_at).astimezone(viewers_timezone)
        datetime_formatted = non_relative_timestamp.strftime("%I:%M %p - %d %b %Y")
        footer_bottom_row.append(html.li(
            html.a(href=self.post_detail_url, data=self.click_data, class_='timestamp u-url', title=datetime_formatted, *[
                html.time(class_='dt-published', datetime=datetime_formatted, *[
                    html.i(class_='icon-time yui3-u'),
                    " " + naturaldate(self.post_a.created_at),
                ])
            ])),
        )

        is_reply = hasattr(self.post_a, 'reply_to') and self.post_a.reply_to
        reply_to_hash = "#" + str(self.post_a.reply_to) if is_reply else ''
        # conversation active?
        if is_reply or (self.post_a.num_replies > 0 and not self.single_post):
            footer_bottom_row.append(
                html.li(class_='in-reply-to yui3-u', *[
                    html.a(href=self.post_detail_url + reply_to_hash, data=self.click_data, title='In Reply To...', *[
                        html.i(class_='icon-comments', **{'aria-label': 'In Reply To...'})
                        ])
                ])
            )

        # reply
        if self.is_authenticated and self.show_reply_button:
            footer_bottom_row.append(self.reply_button())

        if self.show_stream_marker:
            data = {
                'set-stream-marker': ''
            }

            footer_bottom_row.append(
                html.li(class_='show-on-hover yui3-u stream-marker-button', *[
                    html.a(href='#', data=data, *[
                        html.i(class_='icon-bookmark'),
                        ""
                        ])
                ])
            )

        if self.post_a.source and self.show_via_attribution:
            source_link = getattr(self.post_a.source, 'link', None)
            source_name = getattr(self.post_a.source, 'name', None)
            if source_link and source_name:
                footer_bottom_row.append(
                    html.li(class_='show-on-hover post-source yui3-u', *[
                        html.a(href=self.post_a.source.link, rel='nofollow', target='_blank', *[
                            html.i(class_='icon-share'),
                            ' via ' + source_name
                            ])
                    ])
                )

        # crosspost
        annotations = self.post_a.get('annotations', [])
        cp_url = None
        for a in annotations:
            annotation_type = a.get('type')
            if annotation_type == "net.app.core.crosspost":
                cp_url = a.get('value', {}).get('canonical_url')
                if cp_url and not re.match('^https?://', cp_url, re.IGNORECASE):
                    cp_url = "http://" + cp_url

        if cp_url:
            cp_url_display = urlparse(cp_url).netloc
            if cp_url_display.startswith('www.'):
                cp_url_display = cp_url_display[4:]
            footer_bottom_row.append(
                html.li(class_='show-on-hover crossposted-from yui3-u', *[
                    html.a(href=cp_url, target='_blank', *[
                        html.i(class_='icon-random'),
                        ' from ' + cp_url_display
                        ])
                ])
            )

        # report this post to app.net
        if self.show_report_button:
            if self.is_authenticated and self.request.user.adn_user.id != self.post_a.user.id:
                footer_bottom_row.append(
                    html.li(class_='show-on-hover last pull-right yui3-u', *[
                        html.a(href='#report', data={'post-report': ''}, *[
                            html.i(class_='icon-flag'),
                            html.span(class_='t-yui3-u-none m-yui3-u-none', *[' Report']),
                            ])
                    ])
                )

        # mute this user--it's not really an if/else with the delete case so I'm not combining the conditions
        if self.show_mute_button:
            if self.is_authenticated and self.request.user.adn_user.id != self.post_a.user.id and not self.post_a.user.you_muted:
                footer_bottom_row.append(
                    html.li(class_='show-on-hover pull-right yui3-u', *[
                        html.a(href='#mute-user', data={'post-mute-user': ''}, *[
                            html.i(class_='icon-minus-sign'),
                            html.span(class_='t-yui3-u-none m-yui3-u-none', *[' Mute user']),
                            ])
                    ])
                )

        # delete this post
        if self.show_delete_button:
            if self.is_authenticated and self.request.user.adn_user.id == self.post_a.user.id:
                footer_bottom_row.append(
                    html.li(class_='show-on-hover last pull-right yui3-u', *[
                        html.a(href='#delete', data={'post-delete': ''}, *[
                            html.i(class_='icon-remove'),
                            html.span(class_='t-yui3-u-none m-yui3-u-none', *[' Delete']),
                            ])
                    ])
                )

        tree = html.div(class_='post-footer', *[
            html.ul(class_='ul-horizontal unstyled footer-top', *footer_top_row),
            html.ul(class_='ul-horizontal unstyled footer-bottom', *footer_bottom_row)
        ])

        return tree


class PhotoPostPresenter(FeedPostPresenter):
    show_reply_button = False
    show_via_attribution = True

    def generate_media_block(self):
        return ''


class FeedPreviewPresenter(FeedPostPresenter):
    show_reply_button = False
    show_repost_button = False
    show_star_button = False
    show_mute_button = False
    show_report_button = False
    show_delete_button = False


class HiddenFeedPreviewPresenter(FeedPreviewPresenter):
    hidden = True


class FeedPhotoUnderPostPresenter(FeedPostPresenter):

    def generate_post_body(self):
        # Main post text
        text_block = self.generate_post_body_text()
        # media annotation, eg. oEmbed photos
        media_block = self.generate_media_block(default_size=500)

        tree = html.div(class_='body has-media photo-under', *[
            text_block,
            media_block if media_block else ''
        ])

        return tree


class FeedPhotoOverPostPresenter(FeedPostPresenter):

    def generate_post_body(self):
        # Main post text
        text_block = self.generate_post_body_text()
        # media annotation, eg. oEmbed photos
        media_block = self.generate_media_block(default_size=500)

        tree = html.div(class_='body has-media photo-over', *[
            media_block if media_block else '',
            text_block,
        ])

        return tree

POST_PRESENTER_MAP = {
    'default': FeedPostPresenter,
    'photo_under': FeedPhotoUnderPostPresenter,
    'photo_over': FeedPhotoOverPostPresenter,
}


class ChooseFeedPostPresenter(object):

    @classmethod
    def from_item(cls, request, *args, **kwargs):
        presenter = request.GET.get('post_presenter', 'default')
        return POST_PRESENTER_MAP.get(presenter, FeedPostPresenter).from_item(request, *args, **kwargs)


class FeedBackfillButtonPresenter(AbstractPresenter):
    @classmethod
    def from_response(cls, request, min_id, marker_id):
        presenter = cls()
        presenter.request = request
        presenter.min_id = min_id
        presenter.marker_id = marker_id
        return presenter

    def generate_html(self):
        data = {
            'backfill-control': 1,
            'before-id': self.min_id,
            'since-id': self.marker_id,
        }

        return [
            html.div(class_='backfill-container', *[
                html.div(class_='content ta-center', *[
                    html.a(href='#', data=data, *[
                        html.span(class_='yui3-u', *[
                            html.i(class_='icon-circle-arrow-up')
                        ]),
                        html.span(class_='yui3-u text', *[
                            ' Load More'
                        ])
                    ]),
                    html.div(class_='hide spinner-container', *[
                        html.span(class_='loading-spinner hide', *[''])
                    ]),
                ]),
            ])]


class StarPresenter(AbstractPresenter):
    def __init__(self, *args, **kwargs):
        super(StarPresenter, self).__init__(*args, **kwargs)

    @classmethod
    def from_data(cls, request, post_api_obj, *args, **kwargs):
        presenter = cls(*args, **kwargs)
        presenter.request = request
        presenter.post_api_obj = post_api_obj
        presenter.viewer_has_starred = post_api_obj.get('you_starred')
        presenter.is_authenticated = request.user.is_authenticated()

        return presenter

    def generate_html(self):
        if not self.is_authenticated:
            return ''

        star_class = 'icon-star-empty'
        aria_label = 'star'
        if self.viewer_has_starred:
            star_class = 'icon-star'
            aria_label = 'unstar'

        star_inner = html.a(href='#star', data={'star-button': 1, 'starred': int(self.viewer_has_starred), 'post-id': self.post_api_obj['id']}, *[
            html.i(class_=star_class, **{'aria-label': aria_label})
        ])

        return star_inner


class StarFacepilePresenter(AbstractPresenter):
    def __init__(self, *args, **kwargs):
        super(StarFacepilePresenter, self).__init__(*args, **kwargs)

    @classmethod
    def from_data(cls, request, post_api_obj, *args, **kwargs):
        presenter = cls(*args, **kwargs)
        presenter.request = request
        presenter.post_api_obj = post_api_obj
        presenter.starred_by = post_api_obj.starred_by

        return presenter

    def generate_html(self):
        avatar_size = '30s'
        max_num_faces = 5
        li_fn = lambda user: html.li(class_='yui3-u', title=user.username, *[
            html.a(href=smart_reverse(self.request, 'user_detail_view', args=[user.username]), class_='avatar facepile-size', style={'background-image': 'url(%s)' % user.avatar_image.get(avatar_size, '')})
        ])
        tree = html.ul(
            *[li_fn(user) for user in self.starred_by[:max_num_faces]]
        )
        return tree


class RepostButtonPresenter(AbstractPresenter):
    def __init__(self, *args, **kwargs):
        super(RepostButtonPresenter, self).__init__(*args, **kwargs)

    @classmethod
    def from_data(cls, request, post_api_obj, *args, **kwargs):
        presenter = cls(*args, **kwargs)
        presenter.request = request
        presenter.post_api_obj = post_api_obj
        presenter.viewer_has_reposted = post_api_obj.get('you_reposted')
        presenter.is_authenticated = request.user.is_authenticated()

        return presenter

    def generate_html(self):
        if not self.is_authenticated:
            return ''

        if not self.post_api_obj.user or self.request.user.adn_user.id == self.post_api_obj.user.id:
            return ''

        repost_class = 'icon-repost'
        repost_class += ' reposted' if self.viewer_has_reposted else ''
        title = 'remove repost' if self.viewer_has_reposted else 'repost'
        aria_label = title

        repost_inner = html.a(href='#repost', title=title, data={'repost-button': 1, 'reposted': int(self.viewer_has_reposted), 'post-id': self.post_api_obj['id']}, *[
            html.i(class_=repost_class, **{'aria-label': aria_label}),
        ])

        return repost_inner


class FeedInteractionPresenter(AbstractPresenter):
    allowed_actions = ('follow', 'star', 'reply', 'repost', 'broadcast_create', 'broadcast_subscribe', 'broadcast_unsubscribe',
                       'welcome')

    @classmethod
    def from_item(cls, request, coalesced_interaction, show_stream_marker=False, *args, **kwargs):
        presenter = cls(*args, **kwargs)
        presenter.request = request
        presenter.interaction = coalesced_interaction
        presenter.interaction_date = coalesced_interaction.event_date
        presenter.action = coalesced_interaction.action
        presenter.show_stream_marker = show_stream_marker

        return presenter

    def generate_verb(self):
        if self.action == 'follow':
            return 'started following'
        elif self.action == 'star':
            return 'starred'
        elif self.action == 'reply':
            return 'replied to'
        elif self.action == 'repost':
            return 'reposted'
        elif self.action == 'broadcast_create':
            return 'created'
        elif self.action == 'broadcast_subscribe':
            return 'subscribed to'
        elif self.action == 'broadcast_unsubscribe':
            return 'unsubscribed from'
        elif self.action == 'welcome':
            return 'joined'

    def generate_icon(self):
        c = None
        if self.action == 'follow':
            c = 'icon-ok'
        elif self.action == 'star':
            c = 'icon-star'
        elif self.action == 'reply':
            c = 'icon-share-alt'
        elif self.action == 'repost':
            c = 'icon-repost'
        elif self.action in ('broadcast_create', 'broadcast_subscribe', 'broadcast_unsubscribe'):
            c = 'icon-adn-bolt small'
        elif self.action == 'welcome':
            c = 'icon-adn'

        return html.i(class_=(c,)) if c else ''

    def generate_obj_link(self):
        obj = self.interaction.objects[0] if self.interaction.objects else None
        if self.action == 'follow':
            return 'you'
        elif self.action in ('star', 'reply', 'repost'):
            return html.a(href=smart_reverse(self.request, 'post_detail_view', kwargs={'username': self.request.user.username,
                          'post_id': obj['id']}), *['your post'])
        elif self.action in ('broadcast_create', 'broadcast_subscribe', 'broadcast_unsubscribe'):
            return html.a(href=obj.canonical_url, *[obj.title])
        elif self.action == 'welcome':
            return 'App.net'
        return ''

    def _user_link(self, user):
        return smart_reverse(self.request, 'user_detail_view', args=[user['username']], force_qualified=True)

    def _generate_source_user(self, user):
        if user['id'] == self.request.user.adn_user.id:
            return 'You'
        else:
            return html.a(href=self._user_link(user), *[user['username']])

    def generate_source_users(self):
        user_links = map(self._generate_source_user, self.interaction.users)
        return html_list_to_english(user_links)

    def _generate_facepile(self, user):
        facepile_size = 40 * 2
        facepile_img_url = append_query_string(user.avatar_image.url, params={'w': facepile_size, 'h': facepile_size})

        facepile_block = html.a(href=self._user_link(user), *[
            html.img(class_=('interaction-facepile',), alt=user['username'], title=user['username'], src=facepile_img_url)
        ])
        return facepile_block

    def generate_facepiles(self):
        return map(self._generate_facepile, self.interaction.users)

    def generate_html(self):
        if self.action not in self.allowed_actions:
            return ''

        timestamp = html.span(class_=('pull-right', 'timestamp'), title=self.interaction_date.strftime("%I:%M %p - %d %b %Y"), *[
            html.i(class_='icon-time yui3-u'),
            " " + naturaldate(self.interaction_date),
        ])

        text = html.div(*[
            self.generate_icon(),
            self.generate_source_users(),
            ' ',
            self.generate_verb(),
            ' ',
            self.generate_obj_link,
            '.',
            timestamp
        ])

        facepile = html.div(class_=('interaction-facepiles',), *self.generate_facepiles())

        return html.div(class_='post-container interaction subpixel', *[text, facepile])
