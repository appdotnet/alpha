/*global Modernizr:true */
(function () {

    $.fn.setCursorPosition = function (position) {
        if (this.length === 0) {
            return this;
        }
        return $(this).setSelection(position, position);
    };

    $.fn.setSelection = function (selectionStart, selectionEnd) {
        if (this.length === 0) {
            return this;
        }
        var input = this[0];

        if (input.createTextRange) {
            var range = input.createTextRange();
            range.collapse(true);
            range.moveEnd('character', selectionEnd);
            range.moveStart('character', selectionStart);
            range.select();
        } else if (input.setSelectionRange) {
            input.focus();
            input.setSelectionRange(selectionStart, selectionEnd);
        }

        return this;
    };

    $.fn.focusEnd = function () {
        this.setCursorPosition(this.val().length);
        return this;
    };

    var MARKDOWN_LINK_REGEXP = /\[([^\]]+)\]\((\S+(?=\)))\)/;

    var parse_markdown_links = function (text) {
        var oldText;

        function handleReplacement(_, anchor, url, pos) {
            return anchor;
        }

        do {
            oldText = text;
            text = oldText.replace(MARKDOWN_LINK_REGEXP, handleReplacement);
        } while (text !== oldText);

        return text;
    };


    var CharCounter = TAPP.Klass.extend({
        init: function (input, char_count, opts) {
            this.input = input;
            this.char_counter = $(char_count);

            // This tests if the device has touch capabilities.
            // right now that is going to mean mostly phones and tablets
            if ($('html').hasClass('touch')) {
                this.char_counter.addClass('hide');
            }

            this.update_char_count = _.debounce($.proxy(this._update_char_count, this), 50);

            this.initial_char_count = parseInt(this.char_counter.attr('data-total-chars'), 10);

            var default_opts = {
                markdown_support: false,
                perma_text: ''
            };

            opts = $.extend({}, default_opts, opts);

            this.opts = opts;

            this.input.tapp_on('keyup', this.update_char_count);
            this.update_char_count();
        },
        set_total_chars: function (chars) {
            this.char_counter.attr('data-total-chars', chars);
        },
        reset_char_counter: function () {
            this.char_counter.attr('data-total-chars', this.initial_char_count);
        },
        max_chars: function () {
            return parseInt(this.char_counter.attr('data-total-chars'), 10);
        },
        current_chars: function () {
            return parseInt(this.char_counter.attr('data-current-chars'), 10);
        },
        chars_left: function () {
            return parseInt(this.char_counter.attr('data-chars-left'), 10);
        },
        addClass: function (class_) {
            return this.char_counter.addClass(class_);
        },
        removeClass: function (class_) {
            return this.char_counter.removeClass(class_);
        },
        hasClass: function (class_) {
            return this.char_counter.hasClass(class_);
        },
        _update_char_count: function () {
            var text = this.input.val();
            if (this.opts.perma_text) {
                text = text + this.opts.perma_text;
            }

            var value = text;
            if (this.opts.markdown_support) {
                value = parse_markdown_links(value);
            }

            if (!value) {
                return;
            }

            var current_chars = value.length;
            var total_chars = parseInt(this.char_counter.attr('data-total-chars'), 10);
            var chars_left = total_chars - current_chars;

            this.char_counter.attr('data-chars-left', chars_left).text(chars_left);
            this.char_counter.attr('data-current-chars', current_chars);

            this.input.trigger('char-count-updated');
        }
    });

    var MessageCreate = TAPP.Klass.extend({
        init: function () {
            this.success_text = $('[data-success-text]');
            this.submit_button = $('[data-submit-button]');
            this.init_char_counter();
            this.bind_events();
        },
        init_char_counter: function () {},
        events: function () {
            return [
                ['char-count-updated', '[data-message-create] [data-main-message]', 'update_button_state'],
                ['keydown', '[data-message-create] [data-main-message]', 'check_for_cmd_click'],
                ['click', '[data-submit-button]', 'handle_submit']
            ];
        },
        bind_events: function () {
            _.each(this.events(), function (el, index, list) {
                $('body').tapp_on(el[0], el[1], $.proxy(this[el[2]], this));
            }, this);
        },
        timeout: null,
        show_success_text: function () {
            this.success_text.removeClass('hide').removeClass('fade');
            clearTimeout(this.timeout);
            this.timeout = setTimeout($.proxy(function () {
                this.success_text.addClass('fade').addClass('hide');
            }, this), 3000);
        },
        check_for_cmd_click: function (e) {
            var code = e.keyCode || e.which;
            if (code === 13 && (e.metaKey || e.ctrlKey)) {
                var evt = $.Event('click', {target: this.submit_button.get(0)});
                this.handle_submit(evt);
                return false;
            }
        },
        update_button_state: function () {
            var current_chars = this.char_counter.current_chars();
            var chars_left = this.char_counter.chars_left();

            if (current_chars === 0 && !this.has_file) {
                this.submit_button.addClass('disabled');
            } else if (chars_left < 0) {
                this.char_counter.addClass('error');
                this.submit_button.addClass('disabled');
            } else {
                if (this.char_counter.hasClass('error')) {
                    this.char_counter.removeClass('error');
                }

                if (this.submit_button.hasClass('disabled')) {
                    this.submit_button.removeClass('disabled');
                }
            }
        },
        resize_textbox: function (e) {
            var self = $(e.target);
            var textLineHeight = self.data('text-line-height');
            var currentHeight = parseInt(self.attr('data-current-height'), 10);
            var newHeight = this.scrollHeight;

            if (!textLineHeight) { // init this particular textarea
                textLineHeight = parseInt(self.css('line-height'), 10);
                currentHeight = self.height();
                self.css('overflow', 'hidden');
            }

            if (newHeight > currentHeight) {
                newHeight = newHeight + 1 * textLineHeight;
                self.height(newHeight);
                self.attr('data-current-height', newHeight);
            }
        },
        handle_submit: function (e) {
            return TAPP.lock_up($(e.target));
        }
    });

    var PostCreate = MessageCreate.extend({
        events: function () {
            var events_to_bind = MessageCreate.prototype.events.call(this);

            events_to_bind = events_to_bind.concat([
                ['click', '[data-remove-reply]', 'clean_reply_to'],
                ['click', '[data-reply-to]', 'handle_reply_to']
            ]);

            if (!$('html').hasClass('touch')) {
                events_to_bind.push(['keyup', '[data-message-create] [data-main-message]', 'resize_textbox']);
            }

            return events_to_bind;
        },
        init: function () {

            this.post_textarea = $('[data-message-create] [data-main-message]');
            this.in_reply_to = $('[data-message-create] [data-in-reply-to]');
            this.in_reply_to_post_copy = this.in_reply_to.find('[data-post-copy]');
            MessageCreate.prototype.init.call(this);
        },
        init_char_counter: function () {
            this.char_counter = new CharCounter();
            this.char_counter.init(this.post_textarea, '[data-char-counter-for="message"]', {
                markdown_support: true,
                perma_text: page_context.appended_post_url || ''
            });
        },
        clean_reply_to: function () {
            this.in_reply_to.get(0).className = 'hide';
            this.post_textarea.attr('data-in-reply-to-post-id', null);
            return false;
        },

        handle_reply_to: function (e) {
            var reply_to = $(e.target);
            var post = reply_to.closest('[data-post-id]');
            var post_id = post.data('post-id');
            var post_author_username = post.attr('data-post-author-username');
            var viewer_username = page_context.viewer_username;

            this.in_reply_to_post_copy.html(post.html());
            this.in_reply_to_post_copy.addClass(post.get(0).className);
            this.in_reply_to_post_copy.find('.post-footer').remove();
            this.in_reply_to.removeClass('hide');

            var current_post_text = this.post_textarea.val();
            if (!current_post_text.match("@" + post_author_username) && (viewer_username !== post_author_username)) {
                this.post_textarea.val('@' + post_author_username + ' ' + current_post_text);
            }
            this.post_textarea.attr('data-in-reply-to-post-id', post_id);
            $(window).scrollTop(this.post_textarea.scrollTop() + 100);
            this.post_textarea.focusEnd();
            this.char_counter.update_char_count();
            return false;
        },
        showing_error_message: false,
        validate_post: function (text_to_post) {
            var max_chars = this.char_counter.max_chars();
            if (this.showing_error_message) {
                return false;
            }


            if (text_to_post === '') {
                this.showing_error_message = true;
                TAPP.dialogs.error_dialog("You must enter text before posting.", $.proxy(function () {
                    this.showing_error_message = false;
                }, this), {
                    title: "<h3>Sorry</h3>"
                });
                return false;
            }

            if (this.char_counter.current_chars() > max_chars) {
                this.showing_error_message = true;
                TAPP.dialogs.error_dialog("Your post can't be longer than " + max_chars + " characters.", $.proxy(function () {
                    this.showing_error_message = false;
                }, this));
                return false;
            }

            return text_to_post;
        },
        handle_submit: function (e) {
            var finish = MessageCreate.prototype.handle_submit.call(this, e);
            var in_reply_to_id = parseInt(this.post_textarea.attr('data-in-reply-to-post-id'), 10);
            var text_to_post = $.trim(this.post_textarea.val());
            this.create_post(text_to_post, in_reply_to_id).always(finish);

            return true;
        },
        create_post: function (text, in_reply_to_id, annotations) {
            var deferred = $.Deferred();
            var text_to_post = this.validate_post(text);
            if (page_context.appended_post_url) {
                text_to_post = text_to_post + page_context.appended_post_url;
            }
            if (!text_to_post) {
                deferred.reject();
                return deferred;
            }

            var post_obj = {
                text: text_to_post,
                reply_to: in_reply_to_id
            };

            if (annotations) {
                post_obj.annotations = annotations;
            }

            return TAPP.appdotnet_api.post(post_obj).done(
                $.proxy(this.post_success, this)
            ).fail(
                $.proxy(this.post_failure, this)
            );
        },
        post_success: function (response) {
            this.post_textarea.val('');
            this.char_counter.update_char_count();
            this.clean_reply_to();
            // insert posts client-side if either all posts should show up client-side (insert_post_client_side)
            // or the post should show up client-side based on its content (eg. @mention view, #hashtag view)
            var entity_to_match = page_context.insert_post_client_side_based_on_entity;
            var match_fn = function (entity_type) {
                // this looks at one entity type, eg. mentions, and checks if the post contains any that match
                return _.any(response.data.entities[entity_type], function (entity_obj) {
                    return entity_to_match.name === entity_obj.name;
                });
            };
            var insert_post_client_side_based_on_content = entity_to_match && match_fn(entity_to_match.type);
            if (page_context.insert_post_client_side || insert_post_client_side_based_on_content) {
                TAPP.stream_view.insert_item(TAPP.utils.emojify(response.data.html));
            } else if (page_context.refresh_on_post_create) {
                TAPP.stream_view.update_stream();
            } else if (page_context.after_post_goto) {
                window.location = page_context.after_post_goto + '?post_id=' + response.data.id;
            } else {
                this.show_success_text();
            }

            if ($('[data-stream]').children().length <= 0) {
                TAPP.stream_view.update_stream();
            }

            return;
        },
        post_failure: function (xhr) {
            var status_message;
            var error_response;
            try {
                error_response = $.parseJSON(xhr.responseText);
            } catch (e) {
                error_response = null;
            }

            if (xhr.status === 429) {
                status_message = 'Please try your operation again in a moment.';
            } else if (xhr.status === 400 && error_response) {
                if (error_response.meta.error_message.indexOf('Is not a valid url') >= 0) {
                    status_message = 'One of the links in your post is invalid. Edit your post and try again.';
                }
            }

            status_message = status_message || 'There was an error creating that post. Please wait a moment and try again';

            this.showing_error_message = true;
            TAPP.dialogs.error_dialog(status_message, $.proxy(function () {
                this.showing_error_message = false;
            }, this));
            return;
        }
    });

    var MessageCreateAttachmentMixin = {
        init_attachment: function () {
            var container = $('[data-message-create]');
            var upload_widget = new TAPP.FileUploadWidget(container);

            this.uploader = upload_widget.uploader;
            if (this.on_file) {
                container.on('file', $.proxy(this.on_file, this));
            }

            if (this.on_file_reset) {
                container.on('file_reset', $.proxy(this.on_file_reset, this));
            }

            if (this.on_upload_done) {
                container.on('upload_done', $.proxy(this.on_upload_done, this));
            }
        },
        annotations_from_response: function (resp) {
            var annotations;
            if (resp.data.kind === 'image') {
                annotations = [{
                    type: "net.app.core.oembed",
                    value: {
                        "+net.app.core.file": {
                            file_token: resp.data.file_token,
                            format: "oembed",
                            file_id: resp.data.id
                        }
                    }
                }];
            } else {
                annotations = [{
                    type: "net.app.core.attachments",
                    value: {
                        "+net.app.core.file_list": [{
                            file_token: resp.data.file_token,
                            format: "metadata",
                            file_id: resp.data.id
                        }]
                    }
                }];
            }

            return annotations;
        },
        on_file: function (e, file, on_file_read) {
            this.has_file = true;
        },
        on_file_reset: function (e) {
            this.has_file = false;
        }
    };

    var PostCreateWithAttachment = PostCreate.extend($.extend({}, MessageCreateAttachmentMixin, {
        init: function () {
            PostCreate.prototype.init.call(this);
            this.has_file = false;
            if (!Modernizr.filereader) {
                return;
            }
            this.init_attachment();
        },
        create_post: function (text_to_post, in_reply_to_id) {
            var _this = this;
            var deferred = $.Deferred();
            this.submit_button.html('<i class="icon-refresh icon-spin"></i>');
            var super_create_post_call = function (text, annotations) {
                return _this.constructor.__super__.create_post.call(
                    _this, text, in_reply_to_id, annotations
                ).done(deferred.resolve).fail(deferred.reject);
            };

            deferred.always(function () {
                _this.submit_button.html('Post');
            });

            if (this.has_file) {
                this.uploader.upload_state.done($.proxy(function (resp) {
                    var annotations = this.annotations_from_response(resp);
                    var photo_link = _this.post_textarea.data('photo-url');
                    var text = (text_to_post.length > 0) ? text_to_post + " — " + photo_link : photo_link;

                    _this.post_textarea.text(text);

                    super_create_post_call(text, annotations).done(function () {
                        _this.uploader.reset_file_upload();
                    });
                }, this)).fail(function () {
                    deferred.reject();
                });
            } else {
                super_create_post_call(text_to_post);
            }

            return deferred;
        },
        on_file: function (e, file, on_file_read) {
            this.has_file = true;
            var POST_RUNWAY_PADDING = 2; // len('{post_id}') + 2 gives us 10 billion posts for now
            // the user has fewer chars since we add the url which needs base url + dash and spaces
            var fewer_chars = this.post_textarea.data('photo-url').length + 3 + POST_RUNWAY_PADDING;
            this.char_counter.set_total_chars(this.char_counter.initial_char_count - fewer_chars);
            this.char_counter._update_char_count();
            this.update_button_state();
        },

        on_file_reset: function () {
            this.has_file = false;
            this.char_counter.reset_char_counter();
            this.char_counter._update_char_count();
            this.update_button_state();
        }
    }));

    var AlertCreateWithAttachment = MessageCreate.extend($.extend({}, MessageCreateAttachmentMixin, {
        events: function () {
            var events_to_bind = MessageCreate.prototype.events.call(this);
            events_to_bind.push(['char-count-updated', '[data-message-create] [name=subject]', 'update_button_state']);
            return events_to_bind;
        },
        get_channel_id: function () {
            return parseInt($('[data-message-create][data-channel-id]').attr('data-channel-id'), 10);
        },
        init: function () {
            this.message_textarea = $('[data-message-create] [data-main-message]');
            this.subject_input = $('[data-message-create] [name=subject]');
            this.read_more_input = $('[data-message-create] [name=read_more]');
            this.image_preview_container = $('[data-message-create] [data-image-preview]');
            MessageCreate.prototype.init.call(this);
            this.init_attachment();
        },
        init_char_counter: function () {
            this.char_counter = new CharCounter();
            this.char_counter.init(this.message_textarea, '[data-char-counter-for="message"]', {
                markdown_support: true,
                perma_text: page_context.appended_post_url || ''
            });
            this.subject_char_counter = new CharCounter();
            this.subject_char_counter.init(this.subject_input, '[data-char-counter-for="subject"]', {
                markdown_support: true,
                perma_text: page_context.appended_post_url || ''
            });
        },
        get_confirmation_modal: function (send_message) {
            var modal = TAPP.dialogs.markup_dialog('<div class="send-alert-box ta-center"><i class="icon-bullhorn"></i></div>', {
                title: '<h3 class="ta-center">Are you sure you want to send this broadcast?</h3>',
                backdrop: false,
                buttons: {
                    'Cancel': {
                        click: function () {
                            modal.modal("hide");
                            modal.remove();
                        },
                        'class': 'pull-left btn btn-small'
                    },
                    'Send': {
                        click: function () {
                            modal.modal("hide");
                            send_message();
                            modal.remove();
                        },
                        'class': 'pull-right btn btn-small btn-primary'
                    }
                }
            });
            return modal;
        },
        handle_submit: function (e) {
            $('[data-publish-adn-post-failed]').hide();
            var data = this.validate();
            if (data === false) {
                return false;
            }
            var _this = this;
            var send_message = function () {
                var finish = MessageCreate.prototype.handle_submit.call(_this, e);
                var promise = _this.create_message(data);
                promise.always(finish);
            };

            var modal = this.get_confirmation_modal(send_message);
        },
        validate: function () {
            var subject = $.trim(this.subject_input.val());
            var message = $.trim(this.message_textarea.val());
            var read_more = $.trim(this.read_more_input.val());
            var publish_to_adn_posts = $('[name=publish_to_adn_posts]').is(':checked');
            var publish_to_twitter = $('[name=publish_to_twitter]').is(':checked');
            var publish_to_facebook = $('[name=publish_to_facebook]').is(':checked');

            if (!subject || subject === '') {
                this.showing_error_message = true;
                TAPP.dialogs.error_dialog("You must enter a subject.", $.proxy(function () {
                    this.showing_error_message = false;
                }, this), {
                    title: "<h3>Sorry</h3>"
                });
                return false;
            }

            var publish_to = {};
            if (publish_to_facebook) {
                publish_to.facebook = true;
            }

            if (publish_to_twitter) {
                publish_to.twitter = true;
            }

            if (publish_to_adn_posts) {
                publish_to.adn_posts = true;
            }

            return {
                subject: subject,
                message: message,
                read_more: read_more,
                publish_to: publish_to,
                entities: {
                    parse_markdown_links: true
                }
            };
        },
        create_message: function (data) {
            var _this = this;
            var create_message_deferred = $.Deferred();
            this.submit_button.html('<i class="icon-refresh icon-spin"></i>');
            create_message_deferred.always(function () {
                _this.submit_button.html('Send Broadcast');
            });
            var message = {};
            if (data.message && data.message !== '') {
                message.text = data.message;
            } else {
                message.machine_only = true;
            }

            message.annotations = [{
                type: 'net.app.core.broadcast.message.metadata',
                value: {
                    subject: data.subject
                }
            }];

            if (data.read_more && data.read_more !== '') {
                message.annotations.push({
                    type: 'net.app.core.crosspost',
                    value: {
                        canonical_url: data.read_more
                    }
                });
            }

            message.entities = data.entities;
            message.publish_to = data.publish_to;

            var post_message = function (data) {
                return TAPP.appdotnet_api.create_message(_this.get_channel_id(), data).done(function (resp) {
                    _this.post_success(resp);
                    _this.after_create_message(message, resp);
                }).fail(
                    $.proxy(_this.post_failure, _this)
                );
            };

            if (this.has_file) {
                this.uploader.upload_state.done(function (resp) {
                    var annotations = _this.annotations_from_response(resp);

                    message.annotations = message.annotations.concat(annotations);
                    post_message(message).always(function (response) {
                        create_message_deferred.resolve(response);
                    });

                });

            } else {
                post_message(message).always(function (response) {
                    create_message_deferred.resolve(response);
                });
            }

            return create_message_deferred.promise();
        },
        after_create_message: function (message, response) {
            if (message.publish_to.adn_posts) {
                // post to the ADN Posts stream if desired
                var subject = '';
                var fallback_url = '';
                var oembed_annotation;

                _.each(response.data.annotations, function (a) {
                    if (a.type === 'net.app.core.fallback_url' && a.value) {
                        fallback_url = a.value.url;
                    }
                });

                _.each(message.annotations, function (a) {
                    if (a.type === 'net.app.core.broadcast.message.metadata' && a.value) {
                        subject = a.value.subject;
                    } else if (a.type === 'net.app.core.oembed') {
                        if (a.value && a.value['+net.app.core.file']) {
                            oembed_annotation = {};
                            $.extend(oembed_annotation, a);
                            oembed_annotation.value.embeddable_url = fallback_url;
                        }
                    }
                });

                var post_obj = {
                    text: subject + ' ' + fallback_url
                };

                if (oembed_annotation) {
                    post_obj.annotations = [oembed_annotation];
                }

                return TAPP.appdotnet_api.post(post_obj).fail(function (args) {
                    $('[data-publish-adn-post-failed]').show();
                });
            }
        },
        update_button_state: function () {
            var current_chars = this.subject_char_counter.current_chars();
            var chars_left = this.subject_char_counter.chars_left();

            if (current_chars === 0 && !this.has_file) {
                this.submit_button.addClass('disabled');
            } else if (chars_left < 0) {
                this.char_counter.addClass('error');
                this.submit_button.addClass('disabled');
            } else {
                if (this.char_counter.hasClass('error')) {
                    this.char_counter.removeClass('error');
                }

                if (this.submit_button.hasClass('disabled')) {
                    this.submit_button.removeClass('disabled');
                }
            }
        },
        post_success: function (response) {
            this.message_textarea.val('');
            this.subject_input.val('');
            this.read_more_input.val('');
            this.uploader.reset_file_upload();
            this.char_counter.update_char_count();
            this.subject_char_counter.update_char_count();

            this.show_success_text(response);


            return;
        },
        post_failure: function (xhr) {
            var status_message;
            var error_response;
            try {
                error_response = $.parseJSON(xhr.responseText);
            } catch (e) {
                error_response = null;
            }

            if (xhr.status === 429) {
                status_message = 'Please try sending that broadcast again in a moment.';
            } else if (xhr.status === 400 && error_response) {
                if (error_response.meta.error_message.indexOf('Is not a valid url') >= 0) {
                    status_message = 'One of the links in your broadcast is invalid. Edit your alert and try again.';
                }
            }

            status_message = status_message || 'There was an error creating that broadcast. Please wait a moment and try again';

            this.showing_error_message = true;
            TAPP.dialogs.error_dialog(status_message, $.proxy(function () {
                this.showing_error_message = false;
            }, this));
            return;
        },
        on_file_reset: function () {
            this.has_file = false;
            this.image_preview_container.addClass('hide');
        },
        on_upload_done: function (e, resp) {
            var img = $('<img/>').attr('src', resp.data.url);
            this.image_preview_container.html(img).removeClass('hide');
        }
    }));


    var TweetCreate = MessageCreate.extend({
        events: function () {
            var events_to_bind = MessageCreate.prototype.events.call(this);

            if (!$('html').hasClass('touch')) {
                events_to_bind.push(['keyup', '[data-message-create] [data-main-message]', 'resize_textbox']);
            }

            return events_to_bind;
        },
        init: function () {

            this.tweet_textarea = $('[data-message-create] [data-main-message]');
            MessageCreate.prototype.init.call(this);
        },
        init_char_counter: function () {
            this.char_counter = new CharCounter();
            this.char_counter.init(this.tweet_textarea, '[data-char-counter-for="tweet"]', {
                markdown_support: false,
                perma_text: page_context.appended_post_url || ''
            });
        },
        showing_error_message: false,
        validate_post: function (text_to_post) {
            var max_chars = this.char_counter.max_chars();
            if (this.showing_error_message) {
                return false;
            }

            if (text_to_post === '') {
                this.showing_error_message = true;
                TAPP.dialogs.error_dialog("You must enter text before posting.", $.proxy(function () {
                    this.showing_error_message = false;
                }, this), {
                    title: "<h3>Sorry</h3>"
                });
                return false;
            }

            if (this.char_counter.current_chars() > max_chars) {
                this.showing_error_message = true;
                TAPP.dialogs.error_dialog("Your post can't be longer than " + max_chars + " characters.", $.proxy(function () {
                    this.showing_error_message = false;
                }, this));
                return false;
            }

            return text_to_post;
        },
        handle_submit: function (e) {
            var finish = MessageCreate.prototype.handle_submit.call(this, e);
            var text_to_post = $.trim(this.tweet_textarea.val());
            this.create_post(text_to_post).always(finish);

            return true;
        },
        create_post: function (text, annotations) {
            var deferred = $.Deferred();
            var text_to_post = this.validate_post(text);
            if (page_context.appended_post_url) {
                text_to_post = text_to_post + page_context.appended_post_url;
            }
            if (!text_to_post) {
                deferred.reject();
                return deferred;
            }

            var post_obj = {
                action: 'send_tweet',
                tweet_text: text_to_post
            };
            var _this = this;
            return $.post(window.location, post_obj).done(function (response) {
                if (response && response.result === 'error') {
                    $.proxy(_this.post_failure, _this)(response);
                    return;
                }
                $.proxy(_this.post_success, _this)(response);
            }).fail(
                $.proxy(this.post_failure, this)
            );
        },
        post_success: function (response) {
            this.tweet_textarea.val(page_context.pre_tweet_text || '');
            this.char_counter.update_char_count();

            this.show_success_text();
            $(this).trigger('tweet-success', response);
            return;
        },
        post_failure: function (xhr) {
            TAPP.dialogs.error_dialog();
            return;
        }
    });

    // Export classes onto TAPP
    TAPP.AlertCreateWithAttachment = AlertCreateWithAttachment;
    TAPP.MessageCreateAttachmentMixin = MessageCreateAttachmentMixin;
    TAPP.TweetCreate = TweetCreate;

    TAPP.post_create = {
        init: function () {
            var post_create;
            if (Modernizr.filereader && page_context.permit_attachments) {
                post_create = new PostCreateWithAttachment();
            } else {
                post_create = new PostCreate();
            }

            post_create.init();
        },
        alert_init: function () {
            var alert_create = new AlertCreateWithAttachment();
            alert_create.init();
        }
    };

}());
