/* globals Modernizr: true */
(function () {
    // Set up the App.net api for all other modules to use
    var appdot_net_options = $.extend({}, page_context.api_options, {
        no_globals: true
    });


    var DEFAULT_PJAX_CONF = {
        container: '#pjax-container',
        push: true,
        timeout: 10000
    };

    // For response comparison
    if ($.pjax && $.pjax.defaults) {
        $.pjax.defaults.version = page_context.build_info;
    }

    $(window).on('resize', _.debounce(Modernizr.test_media_queries, 50));

    TAPP.pau = {
        init_pau: function () {
            this.intercept_links();
            TAPP.utils.handle_resize();
            this.search_bar();

            $('meta[name=viewport]').attr('content', 'width=device-width, initial-scale=1, maximum-scale=1');
        },
        unload: function () {
            $.fn.affix.unload();
        },
        init_fixed_nav: function () {
            var sidebar_fixed = $('.sidebar-fixed-part');
            var sidebar_offset = parseInt(sidebar_fixed.data('fixed-offset'), 10);
            sidebar_fixed.affix(sidebar_offset);
            $('.create-an-account').affix(0);
        },
        init_placeholder: function () {
            $('input[placeholder], textarea[placeholder]').placeholder();
        },
        search_bar: function () {
            $('body').tapp_on('submit', '[data-search-bar-form]', function () {
                var text_input = $(this).closest('[data-search-bar-form]').find('input[type="text"]');
                if (!$.trim(text_input.val())) {
                    return false;
                }
            });
        },
        intercept_links: function () {
            var _this = this;
            // Intercept links
            $('body').tapp_on('click.intercept_links', 'a', function (event) {
                var link = $(this);
                var url = link.attr('href');
                var pjax_url = link.data('pjax-url');
                var link_location = link.get(0);

                if (pjax_url) {
                    url = pjax_url;
                    var a = document.createElement('a');
                    a.href = url;
                    link_location = a;
                }

                // Ignore cross origin links
                if (location.host !== link_location.host) {
                    return true;
                }

                if (event.which > 1 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
                    return true;
                }

                if (url && !link.attr('target') && url.substring(0, 1) !== '#' && url.substring(0, 11) !== 'javascript:' && !link.data('non-pjax')) {
                    return _this.pjax_load_page({url: url});
                }
            });
        },
        pjax_load_page: function (pjax_conf) {
            var conf = $.extend({}, DEFAULT_PJAX_CONF, pjax_conf);
            $.pjax(conf);
            return false;
        },
        scroll_to: function (el) {
            // scroll into view, keep in mind fixed top nav, banners, etc.
            var fixed_top_offset = 60;
            var result = $.Deferred();
            if ($.pjax.scrolling) {
                result.resolve();
                return result;
            }
            TAPP.utils.on_window_load(function () {
                $('html, body').animate({scrollTop: el.offset().top - fixed_top_offset}, 50, function () {
                    result.resolve();
                });
            });
            return result;
        },
        get_post_el_from_id: function (post_id) {
            var repost = $('[data-post-parent-id=' + post_id + ']');
            var post = $('[name=' + post_id + ']');
            post = (repost.length) ? repost : post;

            return post;
        },
        scroll_post_into_view: function (post_id, highlight_class) {
            var post = this.get_post_el_from_id(post_id);
            if (post.length && !$.pjax.popstate) {
                if (highlight_class) {
                    post.addClass(highlight_class);
                }
                return this.scroll_to(post);
            }
            var result = $.Deferred();
            result.resolve();
            return result;
        },
        zoom_to_post: function () {
            var hash = window.location.hash;
            var post_id = hash.substr(1, hash.length);
            var highlight_class = 'highlight';

            if (!post_id) {
                post_id = page_context.post_id;
                highlight_class = '';
            }

            return this.scroll_post_into_view(post_id, highlight_class);
        },
        init_block_user: function () {
            var block_user = function (link, user_id, username, old_state) {
                var finish = TAPP.lock_up(link);
                var new_state = old_state === 1 ? 0 : 1;
                var block_method = new_state === 0 ? TAPP.appdotnet_api.unblock_user : TAPP.appdotnet_api.block_user;
                var follow_buttons = $('[data-follow-btn][data-user-id="' + user_id + '"]');
                var posts = $('[data-post-author-id="' + user_id + '"]');
                posts.addClass('hide');

                $('[data-block-help]').toggleClass('blocked');
                link.attr('data-block-status', new_state).toggleClass('blocked');
                block_method.call(TAPP.appdotnet_api, user_id).always(finish).fail(function () {
                    link.attr('data-block-status', old_state).toggleClass('blocked');
                    TAPP.dialogs.error_dialog('We were unable to block ' + username + '. Wait a moment, and try again');
                    posts.removeClass('hide');
                    return;
                }).done(function () {
                    posts.remove();
                    follow_buttons.each(function (index, button) {
                        var $button = $(button);
                        if (parseInt($button.attr('data-follow-status'), 10) === 1) {
                            TAPP.follow.update_follow_state($button, 0, $button.closest('[data-follow-details]'));
                        }
                    });
                });
            };

            $('body').tapp_on('click', '[data-block-user]', function () {
                var link = $(this);
                var old_state = parseInt(link.attr('data-block-status'), 10);
                var user_id = link.data('user-id');
                var username = link.data('username');

                if (old_state === 1) {
                    // no warning
                    block_user(link, user_id, username, old_state);
                } else {
                    var my_dialog;
                    var buttons = {
                        "Cancel": {
                            click: function () {
                                my_dialog.remove();
                                return false;
                            }
                        },
                        "Block": {
                            click: function () {
                                block_user(link, user_id, username, old_state);
                                my_dialog.remove();
                                return false;
                            },
                            text: "Block",
                            'class': 'btn btn-small btn-danger'
                        }
                    };

                    var dialog_conf = {
                            title: "<strong>Block " + username + "</strong>",
                            buttons: buttons
                        };

                    my_dialog = TAPP.dialogs.markup_dialog('Are you sure you want to block ' + username + '? You will no longer be able to follow or interact with each other on App.net.', dialog_conf);

                    my_dialog.show();
                }

                $('.user-preferences-dropdown').dropdown('toggle');
                return false;
            });
        },
        mute_user: function (link, user_id, username, old_state, remove_posts) {
            var mute_user = function (link, user_id, username, old_state, remove_posts) {
                remove_posts = remove_posts && old_state === 0;
                if (remove_posts) {
                    var posts = $('[data-post-author-id="' + user_id + '"]');
                    posts.addClass('hide');
                }

                var finish = TAPP.lock_up(link);
                var new_state = old_state === 1 ? 0 : 1;
                var mute_method = new_state === 0 ? TAPP.appdotnet_api.unmute_user : TAPP.appdotnet_api.mute_user;

                $('[data-mute-help]').toggleClass('muted');
                link.attr('data-mute-status', new_state).toggleClass('muted');
                mute_method.call(TAPP.appdotnet_api, user_id).always(finish).fail(function () {
                    link.attr('data-mute-status', old_state).toggleClass('muted');
                    if (remove_posts) {
                        posts.removeClass('hide');
                    }

                    TAPP.dialogs.error_dialog('We were unable to mute ' + username + '. Wait a moment, and try again');
                    return;
                }).done(function () {
                    if (remove_posts) {
                        // When things are successfully deleted on the server
                        // remove them all the way from the client
                        posts.remove();
                    }
                });
            };

            if (old_state === 1) {
                // no warning
                mute_user(link, user_id, username, old_state, remove_posts);
            } else {
                var my_dialog;
                var buttons = {
                    "Cancel": {
                        click: function () {
                            my_dialog.remove();
                            return false;
                        }
                    },
                    "Mute": {
                        click: function () {
                            mute_user(link, user_id, username, old_state, remove_posts);
                            my_dialog.remove();
                            return false;
                        },
                        text: "Mute",
                        'class': 'btn btn-danger btn-small'
                    }
                };

                var dialog_conf = {
                        title: "<strong>Mute " + username + "</strong>",
                        buttons: buttons
                    };

                my_dialog = TAPP.dialogs.markup_dialog('Are you sure you want to mute ' + username + '? This action will hide all of their posts from your feeds and block any @mentions that user directs toward you.', dialog_conf);

                my_dialog.show();
            }
        },
        init_mute_user: function () {
            $('body').tapp_on('click', '[data-mute-user]', function () {
                var link = $(this);
                var old_state = parseInt(link.attr('data-mute-status'), 10);
                var user_id = link.data('user-id');
                var username = link.data('username');

                TAPP.pau.mute_user(link, user_id, username, old_state, false);
                $('.user-preferences-dropdown').dropdown('toggle');
                return false;
            });
        },
        promote_related_broadcasts_dialog: function () {
            var dialog_html = $('[data-promote-related-broadcasts-html]').html();
            var dialog_title = $('[data-promote-related-broadcasts-title]').html();
            var show_download_button = !!$('[data-promote-related-broadcasts-show-download-button]').length;
            var download_url = $('[data-promote-related-broadcasts-download-url]').data('promote-related-broadcasts-download-url');
            var creator_id = $('[data-related-broadcasts-user-id]').data('related-broadcasts-user-id');
            var event_props = {
                "show_download_button": show_download_button,
                "creator_id": creator_id
            };
            var dialog;
            var dialog_params = {
                'title': dialog_title,
                'modal_classes': 'promote-related-broadcasts'
            };
            if (show_download_button) {
                dialog_params.buttons = {
                    "Download the Free App": {
                        click: function () {
                            dialog.remove();

                            TAPP.event_tracking.track_event('cross-promote-broadcast-download-click', event_props, function () {
                                window.location.href = download_url;
                            });
                            return false;
                        },
                        'class': 'btn btn-primary related-broadcasts-button'
                    }
                };
            }
            dialog = TAPP.dialogs.markup_dialog(dialog_html, dialog_params);
            dialog.show();
            TAPP.event_tracking.track_event('cross-promote-broadcast-view', event_props);
        },
        init_promote_related_broadcasts: function () {
            var show_download_button = !!$('[data-promote-related-broadcasts-show-download-button]').length;
            var creator_id = $('[data-related-broadcasts-user-id]').data('related-broadcasts-user-id');
            $('body').tapp_on('click', '[data-promote-related-broadcasts-channels-list] [data-subscribe-btn]', function () {
                TAPP.event_tracking.track_event('cross-promote-broadcast-subscribe-click', {
                    "show_download_button": show_download_button,
                    "creator_id": creator_id
                });
            });
        },
        interstitial: function () {
            var adn_hostname = window.location.hostname.split('.').slice(-2).join('.');
            $.cookie('seen_interstitial', page_context.timestamp, {
                expires: 365,
                path: '/',
                domain: '.' + adn_hostname
            });
            // TAPP.event_tracking.track_event('interstitial-view');
        }
    };

    TAPP.register_post_load_hooks({
        'init_pau': TAPP.pau.init_pau,
        'init_placeholder': TAPP.pau.init_placeholder,
        'zoom_to_post': TAPP.pau.zoom_to_post
    }, TAPP.pau);
}());
