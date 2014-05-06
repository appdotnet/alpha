window.APPDOTNET = (function () {

    var default_options = {
        api_base_url: 'https://api.app.net/',
        enabled_migrations: ['disable_min_max_id', 'response_envelope', 'follow_pagination', 'pagination_ids']
    };

    var API = {

        init: function (options) {
            this.options = $.extend({}, default_options, options);
            this.options.root_url = this.options.api_base_url;

            if (this.options.no_globals) {
                // IE doesn't support deleting things on window
                // like this. So, catch and throw away those errors.
                try {
                    delete window.APPDOTNET;
                } catch (err) {}
            }

            return this;
        },

        request: function (location, ajax_options) {

            ajax_options.url = this.options.root_url + location;
            var headers = {};
            if (this.options.enabled_migrations) {
                var migrations = $.map(this.options.enabled_migrations, function (val, i) {
                    return val + '=1';
                });
                headers['X-ADN-Migration-Overrides'] = migrations.join('&');
            }

            if (this.options.avt) {
                headers['X-AVT'] = this.options.avt;
            }

            ajax_options.beforeSend = function (xhr) {
                _.each(headers, function (val, header) {
                    xhr.setRequestHeader(header, val);
                });
            };
            return $.ajax(ajax_options);
        },

        convert_to_json: function (options) {
            options.contentType = "application/json";
            options.dataType = "json";
            options.data = JSON.stringify(options.data);

            return options;
        },

        post: function (post_obj) {
            var options = {
                type: 'POST',
                data: post_obj
            };

            return this.request('posts?include_post_annotations=1', this.convert_to_json(options));
        },

        follow: function (user_id, new_state) {
            var options = {
                data: {
                    user_id: user_id
                }
            };
            if (new_state === 1) {
                // performing a follow
                options.type = 'POST';
            } else if (new_state === 0) {
                // performing an unfollow
                options.type = 'DELETE';
            } else {
                throw "Invalid follow state.";
            }
            return this.request('users/' + user_id + '/follow', options);
        },
        delete_post: function (post_id) {
            var options = {
                type: 'DELETE'
            };

            var url = 'posts/' + post_id;

            return this.request(url, options);
        },
        report_post: function (post_id, reason) {
            var options = {
                type: 'POST',
                data: {
                    reason: reason
                }
            };

            return this.request('posts/' + post_id + '/report', this.convert_to_json(options));
        },
        mute_user: function (user_id) {
            var options = {
                type: 'POST'
            };

            var url = 'users/' + user_id + '/mute';

            return this.request(url, options);
        },
        unmute_user: function (user_id) {
            var options = {
                type: 'DELETE'
            };

            var url = 'users/' + user_id + '/mute';

            return this.request(url, options);
        },
        block_user: function (user_id) {
            var options = {
                type: 'POST'
            };

            var url = 'users/' + user_id + '/block';

            return this.request(url, options);
        },
        unblock_user: function (user_id) {
            var options = {
                type: 'DELETE'
            };

            var url = 'users/' + user_id + '/block';

            return this.request(url, options);
        },

        star_post: function (post_id, new_state) {
            var options = {};

            if (new_state === 1) {
                // performing a star
                options.type = 'POST';
            } else if (new_state === 0) {
                // performing an unstar
                options.type = 'DELETE';
            } else {
                throw "Invalid star state.";
            }

            return this.request('posts/' + post_id + '/star', options);
        },
        repost_post: function (post_id, new_state) {
            var options = {};

            if (new_state === 1) {
                // performing a repost
                options.type = 'POST';
            } else if (new_state === 0) {
                // deleting a repost
                options.type = 'DELETE';
            } else {
                throw "Invalid repost state.";
            }

            return this.request('posts/' + post_id + '/repost', options);

        },
        update_stream_marker: function (stream_name, post_id) {
            var options = {
                type: "POST",
                data: {
                    name: stream_name,
                    id: post_id
                }
            };

            return this.request('posts/marker', this.convert_to_json(options));
        },
        text_process: function (text) {
            var options = {
                type: "POST",
                data: {
                    text: text
                }
            };

            return this.request('text/process', this.convert_to_json(options));
        },
        file_create: function (form_data, progress) {
            var options = {
                type: "POST",
                data: form_data,
                cache: false,
                contentType: false,
                processData: false,
                progress: progress
            };

            return this.request('files', options);
        },
        file_delete: function (file_id, file_token) {
            var options = {
                type: "DELETE"
            };
            var params = '';
            if (file_token) {
                params = '?' + jQuery.param({file_token: file_token});
            }

            var url = 'files/' + file_id + params;

            return this.request(url, options);
        },
        subscribe_channel: function (channel_id, new_state) {
            var options = {};

            if (new_state === 1) {
                // subscribe to a channel
                options.type = 'POST';
            } else if (new_state === 0) {
                // unsubscribe from a channel
                options.type = 'DELETE';
            } else {
                throw "Invalid subscribe state.";
            }

            var url = 'channels/' + channel_id + '/subscribe';

            return this.request(url, options);
        },
        recommend_app: function (app_id, new_state) {
            var options = {};

            if (new_state === 1) {
                // subscribe to a channel
                options.type = 'POST';
            } else if (new_state === 0) {
                // unsubscribe from a channel
                options.type = 'DELETE';
            } else {
                throw "Invalid recommend state.";
            }

            var url = 'directory/apps/' + app_id + '/recommend';

            return this.request(url, options);
        },
        create_message: function (channel_id, data) {
            var options = {
                type: 'POST',
                data: data
            };

            var url = 'channels/' + channel_id + '/messages?include_annotations=1';

            return this.request(url, this.convert_to_json(options));
        }
    };

    TAPP.appdotnet_api = API.init(page_context.api_options);

    return API;

}());
