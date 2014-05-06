/*globals mixpanel:true, console:true */
(function () {
    var debounced = {};
    var event_queue = [];
    TAPP.event_tracking = {
        fire_off_event: function (event_name, properties, callback) {
            /* disable_mixpanel is view level switch for turning mixpanel on, or off */
            if (page_context.disable_mixpanel || !window.mixpanel) {
                return;
            }
            var timeout;
            var resolve_callback = function () {
                clearTimeout(timeout);
                if (callback) {
                    callback();
                }
            };

            if (properties.user_id) {
                mixpanel.name_tag(properties.user_id);
            }

            mixpanel.track(event_name, properties, function () {
                resolve_callback();
            });

            // wait a limited time for mixpanel to finish before calling callback
            if (callback) {
                timeout = setTimeout(callback, 300);
            }

            if (page_context.console_log_mixpanel) {
                console.log(event_name + ', ' + JSON.stringify(properties));
            }

        },
        mixpanel_process_event_queue: function (callback) {
            var cb = function () {
                event_queue = [];
                callback();
            };
            $.waitForFuncs(event_queue, TAPP.event_tracking.fire_off_event, cb);
        },
        mixpanel_empty_event_queue: function () {
            event_queue = [];
        },
        mixpanel_global_metadata: function () {
            var props = {
                'omo_user_id': page_context.omo_user_id,
                'href': window.location.href
            };
            if (page_context.omo_user_id) {
                props.distinct_id = page_context.omo_user_id;
            } else {
                props.distinct_id = page_context.cookie_value;
            }

            if (page_context.mixpanel_data) {
                $.extend(props, page_context.mixpanel_data);
            }

            var metadata = {};

            // if those defaults are undefined we shouldn't pass them to mixpanel
            _.each(props, function (value, key) {
                if (typeof(value) !== 'undefined') {
                    metadata[key] = value;
                }
            });

            return metadata;
        },
        track_event: function (event_name, properties, callback) {
            var metadata = this.mixpanel_global_metadata();
            if (properties) {
                $.extend(metadata, properties);
            }
            return this.fire_off_event(event_name, metadata, callback);
        },
        track_event_server_side: function (event_name, properties, timeout) {
            var data = {
                action: 'receive_event',
                event_name: event_name
            };

            if (properties) {
                $.extend(data, properties);
            }

            var ajax_def = {
                type: "POST",
                url: ("" + window.location),
                data: data
            };

            if (timeout) {
                ajax_def.timeout = timeout;
            }

            return $.ajax(ajax_def);
        },
        track_from_html_attr: function () {
            $('body').on('click', '[data-track-click]', function () {
                var link = $(this);
                var go_to = link.attr('href');
                var event_name = link.data('track-click');
                var properties = link.data('track-properties');
                var server_side  = link.data('track-server-side');
                if (server_side) {
                    TAPP.event_tracking.track_event_server_side(event_name, properties, 300).always(function () {
                        if (go_to) {
                            window.location.href = go_to;
                        }
                    });
                } else {
                    TAPP.event_tracking.track_event(event_name, properties, function () {
                        if (go_to) {
                            window.location.href = go_to;
                        }
                    });
                }
                return false;
            });
            $('[data-track-seen]').each(function (idx, elem) {
                var $elem = $(elem);
                var event_name = $elem.data('track-seen');
                var properties = $elem.data('track-properties');
                TAPP.event_tracking.track_event(event_name, properties);
            });
        }
    };

    TAPP.register_post_load_hooks({
        'track_event': TAPP.event_tracking.track_event,
        'track_from_html_attr': TAPP.event_tracking.track_from_html
    }, TAPP.event_tracking);

    TAPP.conditional_bindings.add('[data-track-click]', function () {
        TAPP.event_tracking.track_from_html_attr();
    });

}());


