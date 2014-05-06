
from django.middleware.csrf import get_token

from paucore.utils.presenters import AbstractPresenter, html
from paucore.utils.python import memoized_property
from paucore.utils.web import smart_reverse

from pau.presenters.feed import build_tree_from_text_entity_pack


class UserFollowPresenter(AbstractPresenter):
    avatar_size = 57

    @classmethod
    def from_data(cls, request, is_following, target_id, target_username, target_description_dict,
                  target_avatar, button_classes=None, is_onboarding=False, click_data=None, show_follow_buttons=True,
                  *args, **kwargs):
        presenter = cls()
        presenter.request = request
        presenter.is_following = is_following
        presenter.target_id = target_id
        presenter.target_description = target_description_dict
        presenter.target_username = target_username
        presenter.target_avatar = target_avatar
        presenter.button_classes = button_classes
        presenter.is_onboarding = is_onboarding
        presenter.click_data = click_data
        presenter.show_follow_buttons = show_follow_buttons

        presenter.target_user_detail_url = smart_reverse(
            request, 'user_detail_view', args=[presenter.target_username]
        )

        return presenter

    @classmethod
    def from_item(cls, request, target_user_api_obj, *args, **kwargs):
        presenter = cls.from_data(
            request=request,
            is_following=target_user_api_obj.get('you_follow'),
            target_id=target_user_api_obj.id,
            target_username=target_user_api_obj.username,
            target_description_dict=target_user_api_obj.get('description', {}),
            target_avatar=target_user_api_obj.avatar_image[str(cls.avatar_size) + 's'],
            *args,
            **kwargs
        )

        return presenter

    @classmethod
    def from_user(cls, request, target_user, *args, **kwargs):
        presenter = cls.from_data(
            request=request,
            is_following=target_user.id in request.omo_user.following_pks,
            target_id=target_user.id,
            target_username=target_user.username,
            target_description_dict=target_user.description.for_request(),
            target_avatar=target_user.avatar_image.get_url(width=cls.avatar_size, height=cls.avatar_size, want_https=True),
            *args,
            **kwargs
        )

        return presenter

    @memoized_property()
    def follow_button_presenter(self):
        return FollowButtonPresenter.from_data(
            request=self.request,
            is_following=self.is_following,
            target_id=self.target_id,
            extra_classes=self.button_classes,
            click_data=self.click_data,
        )

    @memoized_property()
    def username_presenter(self):
        return UsernamePresenter.from_data(
            request=self.request,
            target_username=self.target_username,
            target_user_detail_url=self.target_user_detail_url,
            click_data=self.click_data,
        )

    @memoized_property()
    def user_avatar_presenter(self):
        return UserAvatarPresenter.from_data(
            request=self.request,
            target_avatar=self.target_avatar,
            target_user_detail_url=self.target_user_detail_url,
            click_data=self.click_data,
        )

    def generate_html(self):
        classes = ['user-follow-container subpixel']
        if self.is_onboarding:
            classes.append('onboarding')
        tree = html.div(class_=classes, data={'user-id': self.target_id}, *[
            html.div(class_='content', *[
                html.div(class_='media', *[
                    self.user_avatar_presenter.generate_html(),
                ]),
                self.generate_body(),
            ]),
        ])
        return tree

    def generate_body(self):
        tree = html.div(class_='body follow-body', *[
            html.div(class_='post-text user-description-block yui3-u-4-5 t-yui3-u-3-4 m-yui3-u-3-4', *[
                html.div(class_='user-description-block-inner', *[
                    html.span(class_='username', *[self.username_presenter.generate_html()]),
                    build_tree_from_text_entity_pack(self.request, self.target_description),
                ]),
            ]),
            html.div(class_='yui3-u-1-5 t-yui3-u-1-4 m-yui3-u-1-4 ta-right', *[
                self.follow_button_presenter.generate_html()
            ]) if self.show_follow_buttons else ''
        ])
        return tree


class EmailUserPresenter(AbstractPresenter):
    @classmethod
    def from_item(cls, request, email_user, *args, **kwargs):
        presenter = cls()
        presenter.request = request
        presenter.email_user = email_user

        return presenter

    def generate_html(self):
        classes = ['user-follow-container subpixel']
        tree = html.div(class_=classes, *[
            html.div(class_='content', *[
                self.generate_body(),
            ]),
        ])
        return tree

    def generate_body(self):
        tree = html.div(class_='body follow-body', *[
            html.div(class_='post-text user-description-block yui3-u-4-5 t-yui3-u-3-4 m-yui3-u-3-4', *[
                html.div(class_='user-description-block-inner', *[
                    html.span(class_='username', *[self.email_user.email]),
                ]),
            ]),
        ])
        return tree


class UserFollowCompactPresenter(UserFollowPresenter):

    def generate_html(self):
        truncated_description = ' '.join(self.target_description.get('text', '').split())
        if len(truncated_description) > 85:
            truncated_description = truncated_description[:82] + " ..."

        classes = ['user-follow-container compact yui3-u-1-4 m-yui3-u-1']
        if self.is_onboarding:
            classes.append('onboarding')

        tree = html.div(class_=classes, *[
            html.a(class_='x-button close icon-remove muted', href='#',
                   data={'not-interested-btn': 1, 'user-id': self.target_id}, alt='Not Interested'),
            html.div(class_='compact-inner', *[
                html.div(class_='yui3-u-1', *[
                    html.a_or_span(class_='avatar', make_link=not self.is_onboarding,
                                   style={'background-image': 'url(%s)' % self.target_avatar},
                                   href=self.target_user_detail_url),
                ]),
                html.div(class_='username ta-center', *[
                    html.a_or_span(href=self.target_user_detail_url, make_link=not self.is_onboarding, *[
                        self.target_username
                    ]),
                ]),
                html.div(class_='post-text note-style user-description-block yui3-u-1 ta-center', *[
                    html.span(truncated_description),
                ]),
                html.div(class_='follow-button-container ta-center', *[
                    self.follow_button_presenter.generate_html()
                ]),
            ])
        ])

        return tree


class FollowButtonPresenter(AbstractPresenter):
    default_button_classes = ['btn btn-small', 'follow-btn']

    @classmethod
    def from_data(cls, request, is_following, target_id, extra_classes=None, show_for_unauthenticated=False,
                  click_data=None, *args, **kwargs):
        presenter = cls(*args, **kwargs)
        presenter.request = request
        presenter.target_id = target_id
        presenter.is_following = is_following
        presenter.extra_classes = extra_classes
        presenter.show_for_unauthenticated = show_for_unauthenticated
        presenter.click_data = click_data or {}
        presenter.is_authenticated = request.user.is_authenticated()

        return presenter

    @classmethod
    def from_user_api_obj(cls, request, target_user_api_obj, extra_classes=None, show_for_unauthenticated=False, *args, **kwargs):
        presenter = cls.from_data(
            request=request,
            is_following=target_user_api_obj.get('you_follow'),
            target_id=target_user_api_obj.id,
            extra_classes=extra_classes,
            show_for_unauthenticated=show_for_unauthenticated,
        )

        return presenter

    def unauthenticated_button(self):
        csrf_token = get_token(self.request)
        tree = html.form(method='POST', *[
            html.input(type='hidden', name='csrfmiddlewaretoken', value=csrf_token),
            html.input(type='hidden', name='action', value='redirect_to_signup'),
            html.input(type='hidden', name='user_id', value=unicode(self.target_id)),
            html.button(class_=self.default_button_classes + ['btn-primary'], *[
                html.span(class_='text-follow', *[
                    "Follow"
                ])
            ])
        ])

        return tree

    def generate_html(self):
        if not self.is_authenticated and self.show_for_unauthenticated:
            return self.unauthenticated_button()

        if not self.is_authenticated or self.target_id == self.request.user.adn_user.id:
            return ''

        if self.is_following:
            data_follow_status = "1"
            following_class = "following"
        else:
            data_follow_status = "0"
            following_class = ''

        data = {
            'follow-status': data_follow_status,
            'user-id': self.target_id,
            'follow-btn': ''
        }
        data.update(self.click_data)
        classes = self.default_button_classes + [following_class]
        if self.extra_classes:
            classes.extend(self.extra_classes)
        if not self.is_following:
            classes.append('btn-primary')

        tree = html.button(class_=classes, data=data, *[
            html.span(class_='text-follow', *[
                "Follow"
            ]),
            html.span(class_='text-unfollow', *[
                "Unfollow"
            ])
        ])

        return tree


class UsernamePresenter(AbstractPresenter):

    @classmethod
    def from_data(cls, request, target_username, target_user_detail_url, click_data=None, *args, **kwargs):
        presenter = cls(*args, **kwargs)
        presenter.request = request
        presenter.target_username = target_username
        presenter.target_user_detail_url = target_user_detail_url
        presenter.click_data = click_data or {}
        return presenter

    def generate_html(self):
        tree = html.a(href=self.target_user_detail_url, data=self.click_data, *[
            self.target_username
        ])
        return tree


class UserAvatarPresenter(AbstractPresenter):

    @classmethod
    def from_data(cls, request, target_avatar, target_user_detail_url, click_data=None, *args, **kwargs):
        presenter = cls(*args, **kwargs)
        presenter.request = request
        presenter.target_avatar = target_avatar
        presenter.target_user_detail_url = target_user_detail_url
        presenter.click_data = click_data or {}
        return presenter

    def generate_html(self):
        tree = html.a(class_='avatar', style={'background-image': 'url(%s)' % self.target_avatar},
                      href=self.target_user_detail_url, data=self.click_data)
        return tree


class UserAutocompletePresenter(UserFollowPresenter):
    avatar_size = 80

    def generate_html(self):
        icon_url = None
        if self.target_avatar:
            icon_url = self.target_avatar

        return html.div(class_='autocomplete-block', *[
            html.div(class_='content ellipsis', *[
                html.div(class_='media', *[
                    html.img(src=icon_url, width='40', height='40') if icon_url else html.span()
                ]),
                html.span(*[self.target_username]),
                html.br(),
                html.small(class_='muted', *['Account'])
            ])
        ])
