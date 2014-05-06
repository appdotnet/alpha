(function () {

    TAPP.stream_view = {
        init_stream: function () {
            // XXX: Create a way to poll/recive updates for new posts in the stream
            // XXX: Handle actions done on posts
            this.setup_infinte_scroll();
        },
        update_stream: function () {
            TAPP.pau.pjax_load_page({url: window.location.href});
        },
        insert_item: function (item) {
            item.addClass('higlight-fade');
            var stream = $('[data-stream]').prepend(item);
            // Need to wait until the next frame to add the fade-in class
            // FF for some reason needs more then just 1ms.
            setTimeout(function () {
                item.addClass('higlight-fade-in');
            }, 50);
        },
        get_items: function (params) {
            var current_url =  window.location.protocol + '//' + window.location.host + window.location.pathname;
            if (page_context.additional_stream_view_params) {
                $.extend(params, page_context.additional_stream_view_params);
            }
            var new_url = current_url + "?" + $.param(params);

            var response = $.Deferred();

            $.get(new_url).done(function (data) {
                var new_html = $(data);
                var new_stream = new_html.find('[data-stream]');
                var resp = {
                    html: new_stream.html(),
                    before_id: new_stream.data('before-id'),
                    since_id: new_stream.data('since-id'),
                    more: new_stream.data('more')
                };

                response.resolve(resp);
            });

            return response;
        },
        scroll_stream: function (callback) {
            var stream = $('[data-stream]');
            var params = {};
            var done;

            params.before_id = pjax_context.infinte_scroll.before_id || stream.data('before-id');
            // params.since_id = stream.data('since-id');
            var more = (typeof(pjax_context.infinte_scroll.more) !== 'undefined') ? pjax_context.infinte_scroll.more : stream.data('more');
            if (!more) {
                callback();
                return false;
            }

            done = function (resp) {
                pjax_context.infinte_scroll.before_id = resp.before_id;
                // When we get bidirectional streaming setup we will need to do this
                // stream.data('since-id', new_stream.data('since-id'));
                pjax_context.infinte_scroll.more = resp.more;
                stream.append(TAPP.utils.emojify(resp.html));
            };

            this.get_items(params).done(done).done(callback);
        },
        setup_infinte_scroll: function () {
            var loading = false;
            var _window = $(window);
            var _document = $(document);
            var _this = this;
            var window_has_scrolled = false;
            pjax_context.infinte_scroll = pjax_context.infinte_scroll || {};

            var nearBottomOfPage = function () {
                if (loading) {
                    return false;
                }

                var at_bottom = _window.scrollTop() > _document.height() - _window.height() - 800;
                if (at_bottom) {
                    loading = true;
                    $('[data-stream-loader]').removeClass('hide');
                    _this.scroll_stream(function () {
                        $('[data-stream-loader]').addClass('hide');
                        loading = false;
                    });
                }
            };

            /* Scrolling and touch events happen a lot, so we
            need to try to keep what we do inside the event handlers to
            a minimum. */

            var handle_movement = function () {
                window_has_scrolled = true;
            };

            _window.tapp_on('touchstart', function () {
                _window.on('touchmove.scroll', handle_movement);
            });

            _window.tapp_on('touchend', function () {
                _window.off('touchmove.scroll');
            });

            _window.tapp_on('scroll', handle_movement);

            TAPP.setInterval(function () {
                if (window_has_scrolled) {
                    window_has_scrolled = false;
                    nearBottomOfPage();
                }
            }, 100);
        },
        init_mute_user: function () {
            $('body').tapp_on('click', '[data-post-mute-user]', function () {
                var post = $(this).closest('[data-post-id]');
                var username = $(post).data('post-author-username');
                var user_id = $(post).data('post-author-id');

                TAPP.pau.mute_user($('[data-mute-user]'), user_id, username, 0, true);
                return false;
            });
        },
        init_post_report: function () {
            var report_post = function (link, post_id, user_id, reason) {
                var posts = $('[data-post-author-id="' + user_id + '"]');
                var finish = TAPP.lock_up(link);

                posts.addClass('hide');
                TAPP.appdotnet_api.report_post(post_id, reason).always(finish).fail(function () {
                    posts.removeClass('hide');

                    TAPP.dialogs.error_dialog('There was an error while reporting this post. Wait a moment, and try again');
                    return;
                }).done(function () {
                    // When things are successfully deleted on the server
                    // remove them all the way from the client
                    posts.remove();
                });
            };

            $('body').tapp_on('click', '[data-post-report]', function () {
                var link = $(this);
                var post = $(this).closest('[data-post-id]');
                var post_id = $(post).data('post-id');
                var user_id = $(post).data('post-author-id');
                var my_dialog;
                var buttons = {
                    "Cancel": {
                        click: function () {
                            my_dialog.remove();
                        }
                    },
                    "Mute": {
                        click: function () {
                            var modal = $(this).closest('.modal');
                            var reason = $('select', modal).find('option:selected').val();
                            report_post(link, post_id, user_id, reason);
                            my_dialog.remove();
                            return false;
                        },
                        text: "Report this post",
                        'class': 'btn btn-small btn-danger'
                    }
                };

                var dialog_conf = {
                        title: "<strong>Report this post</strong>",
                        buttons: buttons
                    };

                var report_selectlist = $('[data-report-post-form]');
                my_dialog = TAPP.dialogs.markup_dialog(report_selectlist, dialog_conf).show();

                return false;
            });

        },
        init_post_delete: function () {
            var rollback_post_detail_delete = function (post) {
                    var post_content = post.find('.post-content');
                    post_content.html(post.attr('data-redacted'));
                    post.removeClass('deleted');
                };

            var post_detail_delete = function (post) {
                    var post_content = post.find('.post-content');
                    post.attr('data-redacted', post_content.html());
                    post_content.text('[deleted]');
                    post.addClass('deleted');
                };

            var delete_post = function (link, post) {
                var post_id = post.data('post-id');
                var finish = TAPP.lock_up(link);
                var remove = (post.data('post-remove-from-page') === 1) ? true : false;

                if (remove) {
                    post.addClass('hide');
                } else {
                    post_detail_delete(post);
                }

                TAPP.appdotnet_api.delete_post(post_id).always(finish).fail(function () {
                    if (remove) {
                        post.removeClass('hide');
                    } else {
                        rollback_post_detail_delete(post);
                    }

                    TAPP.dialogs.error_dialog('We were unable to delete that post. Wait a moment, and try again');
                    return;
                }).done(function () {

                    // When things are successfully deleted on the server
                    // delete them all the way from the client
                    if (remove) {
                        post.remove();
                    } else {
                        post.attr('data-redacted', null);
                    }
                });
            };

            $('body').tapp_on('click', '[data-post-delete]', function () {
                var link = $(this);
                var post = $(this).closest('[data-post-id]');
                var my_dialog;
                var buttons = {
                    "Cancel": {
                        click: function () {
                            my_dialog.remove();
                        }
                    },
                    "Delete": {
                        click: function () {
                            delete_post(link, post);
                            my_dialog.remove();
                            return false;
                        },
                        text: "Delete",
                        'class': 'btn btn-small btn-danger'
                    }
                };

                var dialog_conf = {
                        title: "<strong>Delete Post</strong>",
                        buttons: buttons
                    };

                my_dialog = TAPP.dialogs.markup_dialog('Are you sure you want to delete this post?', dialog_conf);

                my_dialog.show();

                return false;
            });
        },
        init_star_post: function () {
            $('body').tapp_on('click', '[data-star-button]', function () {
                var target = $(this);
                var icon = $(this).find('i');
                var post_id = $(this).data('post-id');
                var old_state = parseInt(target.attr('data-starred'), 10);
                var new_state = -1;
                if (old_state === 1) {
                    new_state = 0;
                } else if (old_state === 0) {
                    new_state = 1;
                } else {
                    return false;
                }

                var unlock = TAPP.lock_up(target);
                icon.toggleClass('icon-star').toggleClass('icon-star-empty');
                target.attr('data-starred', new_state);

                TAPP.appdotnet_api.star_post(post_id, new_state).always(unlock).fail(function () {
                    icon.toggleClass('icon-star').toggleClass('icon-star-empty');
                    target.attr('data-starred', old_state);
                    var prefix = new_state === '0' ? "un" : "";
                    TAPP.dialogs.error_dialog('Unable to ' +  prefix + 'star this post. Wait a moment, and try again');
                    return;
                });

                return false;
            });
        },
        init_repost: function () {
            var that = this;
            $('body').tapp_on('click', '[data-repost-button]', function () {
                var target = $(this);
                var post_container = target.closest('.post-container');
                var icon = $(this).find('i');
                var post_id = $(this).data('post-id');
                var old_state = parseInt(target.attr('data-reposted'), 10);
                var new_state = -1;
                if (old_state === 1) {
                    new_state = 0;
                } else if (old_state === 0) {
                    new_state = 1;
                } else {
                    return false;
                }

                var unlock = TAPP.lock_up(target);
                var current_title = target.attr('title');
                var new_title = (new_state === 1) ? 'remove repost' : 'repost';

                icon.toggleClass('reposted');
                target.attr('data-reposted', new_state);
                target.attr('title', new_title);
                that.decorate_repost(post_container, new_state);

                TAPP.appdotnet_api.repost_post(post_id, new_state).always(unlock).fail(function () {
                    icon.toggleClass('reposted');
                    target.attr('data-reposted', old_state);
                    target.attr('title', current_title);
                    that.decorate_repost(post_container, old_state);

                    TAPP.dialogs.error_dialog('Unable to ' +  current_title + '. Wait a moment, and try again');
                    return;
                });

                return false;
            });
        },
        decorate_repost: function (post_container, new_state) {
            var post_text = post_container.find('.footer-top');
            var reposted_by = post_container.find('.post-reposted-by');
            var set_reposted_by_html = function (new_html) {
                if (reposted_by.length) {
                    reposted_by.replaceWith(new_html);
                } else {
                    post_text.prepend(new_html);
                }
            };

            var outer_html = function (elem) {
                return $('<p>').append(elem.clone()).html();
            };

            var old_repost_html = post_container.attr('data-old-repost-html');
            if (old_repost_html) {
                post_container.attr('data-old-repost-html', outer_html(reposted_by));
                set_reposted_by_html(old_repost_html);
            } else {
                // save current repost markup
                old_repost_html = outer_html(reposted_by);
                post_container.attr('data-old-repost-html', old_repost_html);

                // replace current markup with new markup
                var new_reposted_by;
                if (new_state === 1) { // you just reposted
                    new_reposted_by = '<div class="post-reposted-by yui3-u"><span class="reposted-by-text"><i class="icon-repost"></i><span> Reposted by <a href="/' + page_context.viewer_username + '">you</a></span></span></div>';
                } else { // you just un-reposted
                    new_reposted_by = '';
                }
                // replace or add the new_reposted_by markup
                set_reposted_by_html(new_reposted_by);
            }
        },
        init_stream_marker: function () {

            TAPP.utils.on_window_load(function () {
                TAPP.pau.scroll_post_into_view(page_context.stream_marker_post_id, 'stream-highlight').done(function () {
                    $(window).trigger('viewport-ready');
                });
            });

            var clicked_load_more = false;
            var backfill = $('[data-backfill-control]');
            var backfill_container = backfill.closest('.backfill-container');
            var _this = this;
            $('body').tapp_on('click', '[data-backfill-control]', function (e) {
                var params = {
                    before_id: backfill.data('before-id'),
                    since_id: parseInt(backfill.attr('data-since-id'), 10),
                    backfill: '0',
                    count: -200
                };
                var button = $(this);
                var spinner_container = button.closest('.content').find('.spinner-container');
                clicked_load_more = true;
                button.addClass('hide');
                spinner_container.removeClass('hide');
                _this.get_items(params).done(function (resp) {
                    backfill_container.after(TAPP.utils.emojify(resp.html));
                    TAPP.pau.scroll_post_into_view(resp.before_id);
                    button.removeClass('hide');
                    spinner_container.addClass('hide');
                    if (resp.more) {
                        backfill.attr('data-since-id', resp.since_id);
                    } else {
                        backfill_container.addClass('hide');
                    }
                });

                return false;
            });

            var update_stream_marker_api = function (stream_marker_name, post_id, unlock, fail) {
                TAPP.appdotnet_api.update_stream_marker(page_context.stream_marker_name, post_id).always(unlock).fail(fail);
            };

            var throttle_update_stream_marker_api = _.debounce(update_stream_marker_api, 10000);

            var update_stream_marker = function (button, report_error, throttle) {
                var post = button.closest('[data-post-id]');
                var parent_post_id = post.data('post-parent-id');
                var post_id = parent_post_id || post.data('post-id');
                var unlock = TAPP.lock_up(button);
                var last_highlighted_post = $('[data-post-id].stream-highlight');
                var last_stream_marker_post_id = page_context.stream_marker_post_id;

                page_context.stream_marker_post_id = post_id;
                last_highlighted_post.removeClass('stream-highlight');
                post.addClass('stream-highlight');

                var fail = function () {
                    last_highlighted_post.addClass('stream-highlight');
                    post.removeClass('stream-highlight');
                    page_context.stream_marker_post_id = last_stream_marker_post_id;
                    if (report_error) {
                        TAPP.dialogs.error_dialog('Unable to update the stream marker. Wait a moment, and try again');
                    }
                };

                var func = (throttle) ? throttle_update_stream_marker_api : update_stream_marker_api;

                return func(page_context.stream_marker_name, post_id, unlock, fail);

            };

            $('body').tapp_on('click', '[data-set-stream-marker]', function (e) {
                var button = $(this);
                update_stream_marker(button, true);
                return false;
            });

            var win = $(window);
            var is_scrolled_into_view = function (elem) {
                var docViewTop = win.scrollTop() + 60;
                var docViewBottom = docViewTop + win.height();
                var elemTop = elem.offset().top;

                return elemTop <= docViewBottom && elemTop >= docViewTop;
            };

            var fire_update_marker = function (e) {
                var posts = $('.post-container');

                if (!posts.length || clicked_load_more) {
                    clicked_load_more = false;
                    return true;
                }
                posts.each(function () {
                    var elem = $(this);

                    if (elem.data('post-id') && is_scrolled_into_view(elem)) {
                        if (parseInt(elem.data('post-id'), 10) <= page_context.stream_marker_post_id) {
                            return false;
                        }
                        var button = $(elem.find('[data-set-stream-marker]'));
                        // XXX: We could do this better, but I am just trying to stop 400's coming from alpha
                        if (!button.length) {
                            return false;
                        }
                        update_stream_marker(button, false, true);

                        return false; // early exit when we find our culprit
                    }
                });
            };

            // Wait like half a second before we start updating scroll position
            $(window).tapp_on('viewport-ready', function () {
                win.tapp_on('scroll', _.debounce(fire_update_marker, 500));
            });
        }
    };

    TAPP.register_post_load_hooks({
        'init_stream': TAPP.stream_view.init_stream,
        'init_post_delete': TAPP.stream_view.init_post_delete,
        'init_mute_user': TAPP.stream_view.init_mute_user,
        'init_post_report': TAPP.stream_view.init_post_report,
        'init_star_post': TAPP.stream_view.init_star_post,
        'init_repost': TAPP.stream_view.init_repost,
        'init_stream_marker': TAPP.stream_view.init_stream_marker
    }, TAPP.stream_view);
}());
