from paucore.utils.presenters import AbstractPresenter, html

from pau.constants import POST_LIMIT
from pau.presenters.widgets import file_upload_progress


class PostCreatePresenter(AbstractPresenter):
    textarea_name = 'post'
    char_count = POST_LIMIT
    success_message = 'Your post has been created.'

    @classmethod
    def from_data(cls, request, btn_action='Post', post_create_pre_text='', reply_to=None, appended_post_url=None, *args, **kwargs):
        presenter = cls(*args, **kwargs)
        presenter.request = request
        presenter.btn_action = btn_action
        presenter.in_reply_to_post_id = reply_to.id if reply_to else None
        if not post_create_pre_text and reply_to and reply_to.get('user') and request.user.is_authenticated() and request.user.adn_user.id != reply_to.user.id:
            post_create_pre_text = '@%s ' % (reply_to.user.username)

        presenter.post_create_pre_text = post_create_pre_text

        presenter.appended_post_url = appended_post_url

        return presenter

    def photo_url_template(self):
        photo_url_template = 'https://photo.app.net/'
        photo_url_template += '{post_id}/1'
        return photo_url_template

    def textarea_data_attrs(self):

        data_attrs = {
            'main-message': 1,
            'text-line-height': 18,
            'current-height': 80,
            'include-attachment': 1,
            'photo-url': self.photo_url_template()
        }

        if self.in_reply_to_post_id:
            data_attrs['in-reply-to-post-id'] = self.in_reply_to_post_id

        return data_attrs

    def generate_textarea(self, placeholder=''):
        data_attrs = self.textarea_data_attrs()
        return html.textarea(class_='editable input-flex', name=self.textarea_name, placeholder=placeholder, tabindex='1', data=data_attrs, *[self.post_create_pre_text])

    def generate_textarea_container(self):
        return html.div(class_='text-area layout-like-p subpixel"', *[
            self.generate_textarea()
        ])

    def generate_in_reply_to_container(self):
        return html.div(class_='hide in-reply-to layout-like-p subpixel', data={'in-reply-to': 1}, *[
            html.div(html.em(*['In Reply To:'])),
            html.div(class_='well-style reply-to', *[
                html.a(href='#', class_='close relative space-5', data={'remove-reply': 1}, *[
                    html.i(class_='icon-remove')
                ]),
                html.div(class_='post-container subpixel', data={'post-copy': 1})
            ])
        ])

    def generate_append_post_url(self):
        return html.div(class_='ta-left', *[
            html.p(*[
                '%s will automatically be appended to your post.' % (self.appended_post_url)
            ])
        ])

    def generate_char_count(self):
        return html.span(class_='char-count', data={'char-counter-for': 'message', 'total-chars': self.char_count, 'current-chars': 0}, *[
            unicode(self.char_count)
        ])

    def generate_bottom_row(self):
        file_upload = file_upload_progress()
        success = html.span(class_='text-success hide', data={'success-text': 1}, *[self.success_message])
        add_photo = html.button(class_='btn-attach-file file-related transition-color', data={'attach-btn': 1}, *[
            html.i(class_='icon-picture'),
            u'Add photo\u2026'
        ])
        char_count = self.generate_char_count()
        create_button = html.button(tabindex='2', data={'submit-button': 1}, class_='btn btn-primary %s-button btn-small disabled' % (self.btn_action.lower()), *[
            self.btn_action
        ])

        return html.grid(*[
            html.div(class_='yui3-u-1-4 ta-left m-yui3-u-none', *[char_count]),
            html.div(class_='yui3-u-3-4 ta-right m-yui3-u-1', *[
                file_upload,
                success,
                add_photo,
                create_button,
            ])
        ])

    def generate_html(self):
        if not self.request.user.is_authenticated():
            return ''

        parts = [self.generate_textarea_container()]
        parts += [self.generate_in_reply_to_container()]
        if self.appended_post_url:
            parts += [self.generate_append_post_url()]

        parts += [self.generate_bottom_row()]

        return html.div(class_='well-plain well-elevated newpost', data={'message-create': 1}, *parts)
