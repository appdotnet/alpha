(function () {
    TAPP.follow = {
        init_follow: function () {
            var _this = this;
            // handle following/unfollowing users
            var handle_follow_btn_click = function (tgt) {
                var target = $(tgt);
                var user_id = target.data('user-id');
                var old_state = parseInt(target.attr('data-follow-status'), 10);
                var new_state;
                if (old_state === 1) {
                    new_state = 0;
                } else {
                    new_state = 1;
                }

                var follow_details = target.closest('[data-follow-details]');

                // optimistic server interaction
                _this.update_follow_state(target, new_state, follow_details);
                TAPP.appdotnet_api.follow(user_id, new_state).fail(function (xhr, status, error) {
                    var resp = JSON.parse(xhr.responseText);
                    _this.update_follow_state(target, old_state, follow_details);
                    if (xhr.status === 507) {
                        TAPP.dialogs.upgrade_dialog(
                            resp.meta.error_message,
                            "Nice! You've followed a bunch of accounts.",
                            function () {
                                window.location = page_context.subscribe_url; // aka 'upgrade' url, not channel subscribe
                            }
                        );
                    } else {
                        TAPP.dialogs.error_dialog("There was a problem " +
                            (new_state === 0 ? "un" : "") + "following" +
                            " this user. Please wait a moment and try again."
                        );
                    }

                }).done(function () {
                    target.trigger('follow-state-change', [new_state]);
                    if (new_state === 1) {
                        _this.after_follow();
                    }
                });
            };
            $('body').tapp_on('click', '[data-follow-btn]', function () {
                handle_follow_btn_click(this);
            });

            var action_and_next_suggestion_ajax = function (action, suggested_users_list, num, user_id) {
                var user_ids_on_page = $.map(suggested_users_list.find('[data-follow-btn]'), function (el, idx) {
                    return $(el).data('user-id');
                });

                var post_data = {
                    action: action,
                    user_ids_on_page: user_ids_on_page,
                    num: num || 1
                };
                if (user_id) {
                    post_data.user_id = user_id;
                }

                var ajax_deferred = $.ajax({
                    url: window.location,
                    type: 'POST',
                    data: post_data
                });
                return ajax_deferred;
            };

            $('body').tapp_on('click', '[data-follow-suggestions] [data-not-interested-btn], [data-follow-suggestions] [data-follow-btn]', function () {
                var target = $(this);
                var suggested_users_list = target.closest('.suggested-users-list');
                var container = target.closest('.user-follow-container');
                var action, user_id, ajax_deferred;
                if (target.is('[data-not-interested-btn]')) {
                    user_id = target.data('user-id');
                    action = 'dont_suggest_user';
                    ajax_deferred = action_and_next_suggestion_ajax(action, suggested_users_list, 1, user_id);
                } else { // follow button
                    action = 'next_suggestion';
                    ajax_deferred = action_and_next_suggestion_ajax(action, suggested_users_list, 1);
                }
                ajax_deferred.done(function (data) {
                    var new_html_arr = data.html;
                    container.replaceWith(new_html_arr[0]);
                });
                return false;
            });

            $('body').tapp_on('click', '[data-refresh-all-suggestions]', function () {
                var action = 'next_suggestion';
                var suggested_users_list = $('.suggested-users-list');
                var ajax_deferred = action_and_next_suggestion_ajax(action, suggested_users_list, 12);
                ajax_deferred.done(function (data) {
                    var new_html_arr = data.html;
                    suggested_users_list.find('.user-follow-container').each(function (idx, elem) {
                        if (new_html_arr.length) {
                            $(elem).replaceWith(new_html_arr.pop());
                        } else {
                            $(elem).hide();
                        }
                    });
                });
                return false;
            });

        },
        update_button_state: function (data_attr, toggle_class, $button, new_state) {
            if (parseInt($button.attr(data_attr), 10) === new_state) {
                return false;
            }

            $button.attr(data_attr, new_state).toggleClass(toggle_class).toggleClass('btn-primary');

            return true;
        },
        update_subscribe_state: function ($button, new_state, subscribe_details) {
            this.update_button_state('data-subscribe-status', 'subscribed', $button, new_state);
        },
        update_recommend_state: function ($button, new_state, recommend_details) {
            this.update_button_state('data-recommend-status', 'recommended', $button, new_state);
        },
        update_follow_state: function ($button, new_state, follow_details) {
            var updated = this.update_button_state('data-follow-status', 'following', $button, new_state);
            if (updated) {
                var delta = new_state === 1 ? 1 : -1;
                TAPP.follow.update_follow_stats(follow_details, delta);
            }
        },
        update_follow_stats: function (follow_details, delta) {
            // nomenclature:
            // follows-to = the follows TO THE CURRENT USER from other users
            // follows-from = the follows FROM THE CURRENT USER to other users
            var follows_to = follow_details.find('.follow-to');
            var follows_to_count_el = follows_to.find('[data-follow-to-count]');
            var old_follows_to_count = parseInt(follows_to_count_el.attr('data-follow-to-count'), 10);
            var follows_to_text = follows_to.find('.text');

            var new_follows_to_count = old_follows_to_count + delta;

            var old_follows_to_text = follows_to_text.text();
            var new_follows_to_text = old_follows_to_text;
            if (old_follows_to_count === 1) {
                new_follows_to_text = " Followers";
            } else if (new_follows_to_count === 1) {
                new_follows_to_text = " Follower";
            }
            follows_to_count_el.text(TAPP.utils.intcomma(new_follows_to_count)).attr('data-follow-to-count', new_follows_to_count);
            follows_to_text.text(new_follows_to_text);
        },
        after_follow: function () {
            if (page_context.promote_related_broadcasts) {
                TAPP.pau.promote_related_broadcasts_dialog();
            }
        },
        intent_follow: function () {
            $('body').tapp_on('follow-state-change', '[data-follow-btn]', function () {
                window.location = page_context.after_follow_goto;
            });
        },
        intent_subscribe: function () {
            $('body').tapp_on('subscribe-state-change', '[data-subscribe-btn]', function () {
                window.location = page_context.after_subscribe_goto;
            });
        },
        init_subscribe: function () {
            var _this = this;
            var handle_subscribe_btn_click = function (tgt) {
                var target = $(tgt);
                var channel_id = target.data('channel-id');
                var old_state = parseInt(target.attr('data-subscribe-status'), 10);
                // One time is if we want the subscribe widget to only record
                // one subscribe event and then mute its self.
                var one_time = parseInt(target.attr('data-one-time'), 10) === 1;
                var changed = parseInt(target.attr('data-changed'), 10) === 1;
                var undo_url = target.attr('data-undo-url');
                if (one_time && changed) {
                    window.open(undo_url, '_blank');
                    return false;
                }
                var new_state;
                if (old_state === 1) {
                    new_state = 0;
                } else {
                    new_state = 1;
                }

                var subscribe_details = target.closest('[data-subscribe-details]');

                // optimistic server interaction
                _this.update_subscribe_state(target, new_state, subscribe_details);
                if (one_time) {
                    target.addClass('subscribed-final');
                    target.attr('data-changed', new_state);
                }
                TAPP.appdotnet_api.subscribe_channel(channel_id, new_state).fail(function (xhr, status, error) {
                    var resp = JSON.parse(xhr.responseText);

                    _this.update_subscribe_state(target, old_state, subscribe_details);
                    if (one_time) {
                        target.removeClass('subscribed-final');
                        target.attr('data-changed', old_state);
                    }
                    TAPP.dialogs.error_dialog("There was a problem " +
                        (new_state === 0 ? "un" : "") + "subscribing" +
                        ". Please wait a moment and try again."
                    );

                }).done(function () {
                    target.trigger('subscribe-state-change', [new_state]);
                    if (new_state === 1) {
                        _this.after_subscribe();
                    }
                }).always(function () {
                    var event_base_name;
                    if (page_context.alert_detail_page) {
                        event_base_name = 'alert-detail';
                    } else if (page_context.channel_detail_page) {
                        event_base_name = 'channel-promo';
                    } else {
                        return;
                    }

                    var action = "subscribe";
                    if (old_state === 1) {
                        action = "unsubscribe";
                    }
                    TAPP.event_tracking.track_event(event_base_name + '-subscribe-click', {
                        'logged_in': !!page_context.omo_user_id,
                        'channel_id': channel_id,
                        'action': action
                    });
                });
            };
            $('body').tapp_on('click', '[data-subscribe-btn]', function () {
                handle_subscribe_btn_click(this);
            });
        },
        after_subscribe: function () {
            if (page_context.subscribe_popup) {
                TAPP.oahu.subscribe_popup();
            }
        },
        init_recommend: function () {
            var _this = this;
            var handle_recommend_btn_click = function (tgt) {
                var target = $(tgt);
                var app_id = target.data('app-id');
                var old_state = parseInt(target.attr('data-recommend-status'), 10);
                var new_state;
                if (old_state === 1) {
                    new_state = 0;
                } else {
                    new_state = 1;
                }

                var recommend_details = target.closest('[data-recommend-details]');

                // optimistic server interaction
                _this.update_recommend_state(target, new_state, recommend_details);
                TAPP.appdotnet_api.recommend_app(app_id, new_state).fail(function (xhr, status, error) {
                    var resp = JSON.parse(xhr.responseText);
                    _this.update_recommend_state(target, old_state, recommend_details);
                    TAPP.dialogs.error_dialog("There was a problem " +
                        (new_state === 0 ? "un" : "") + "recommending" +
                        ". Please wait a moment and try again."
                    );

                }).done(function () {
                    target.trigger('recommend-state-change', [new_state]);
                });
            };
            $('body').tapp_on('click', '[data-recommend-btn]', function () {
                handle_recommend_btn_click(this);
            });
        }
    };

    TAPP.register_post_load_hooks({
        'init_follow': TAPP.follow.init_follow
    }, TAPP.follow);
}());
