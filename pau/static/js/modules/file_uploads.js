(function () {

    (function addXhrProgressEvent($) {
        var originalXhr = $.ajaxSettings.xhr;
        $.ajaxSetup({
            progress: $.noop,
            xhr: function () {
                var req = originalXhr(), that = this;
                if (req && req.upload) {
                    if (typeof req.upload.addEventListener === "function") {
                        req.upload.addEventListener("progress", function (evt) {
                            that.progress(evt);
                        }, false);
                    }
                }
                return req;
            }
        });
    }(jQuery));

    var FileUploader = function (options) {
        this.activator = options.activator;
        this.file_input = options.file_input;
        this.on_file = options.on_file || $.noop;
        this.on_file_reset = options.on_file_reset || $.noop;
        this.on_upload_start = options.on_upload_start || $.noop;
        this.on_progress = options.on_progress || $.noop;
        this.on_upload_done = options.on_upload_done || $.noop;
        this.allow = options.allow || false;
        this.on_disallow = options.on_disallow || $.noop;
        this.max_file_size = options.max_file_size || false;
        this.upload_to = options.upload_to;
        this.extra_data = options.extra_data || [];
        this.upload_on_change = options.upload_on_change || false;
        this.validator = options.validator || $.noop;
        this.upload_state = $.Deferred();
    };

    $.extend(FileUploader.prototype, {
        handle_change: function (e) {
            var file = (e.target.files && e.target.files.length) ? e.target.files[0] : false;
            if (!e.target.files && !file) {
                var button = $(e.target);
                var form = button.closest('form');
                form.get(0).submit();
                return;
            }

            if (!file) {
                return;
            }

            if (this.allow && !this.allow.test(file.type)) {
                this.on_disallow(file);
                return;
            }

            if (this.max_file_size && this.max_file_size < file.size) {
                var max_in_mb = this.max_file_size / 1024 / 1024;
                var file_size_in_mb = Math.round((file.size / 1024 / 1024) * 100) / 100;
                TAPP.dialogs.error_dialog('The max file size is ' + max_in_mb + 'MB. The file you tried to attach was ' + file_size_in_mb + 'MB');
                return;
            }

            this.file = file;
            this.on_file(file, function () {
                var reader = new FileReader();
                var on_file_read = $.Deferred();
                reader.onload = function (e) {
                    on_file_read.resolve(e);
                };
                reader.readAsDataURL(file);

                return on_file_read;
            });
            if (this.upload_on_change) {
                this.upload_file();
            }
        },
        handle_activator_click: function (e) {
            this.file_input.trigger('click');
            return false;
        },
        bind_events: function () {
            this.activator.tapp_on('click.uploader', $.proxy(this.handle_activator_click, this));
            this.bind_file_events();
        },
        bind_file_events: function () {
            this.file_input.tapp_on('change.uploader', $.proxy(this.handle_change, this));
        },
        reset_file_upload: function () {
            this.upload_state = $.Deferred();
            this.file_input.off('change.uploader');
            this.file_input.replaceWith(this.file_input.val('').clone(true));
            this.bind_file_events();
            this.on_file_reset();
        },
        upload_file: function () {
            this.on_upload_start();
            var data = new FormData();
            data.append('content', this.file);
            _.map(this.extra_data, function (el) {
                data.append(el[0], el[1]);
            });

            // Upload to is the actual network deferred
            this.current_upload = this.upload_to(data, $.proxy(function (e) {
                if (e.lengthComputable) {
                    var percent_done = parseInt((e.loaded / e.total * 100), 10);
                    this.on_progress(percent_done);
                }
            }, this));

            this.current_upload.fail($.proxy(function (xhr, status, error) {
                var resp;
                try {
                    resp = JSON.parse(xhr.responseText);
                } catch (err) {
                    resp = {};
                }

                if (resp && xhr.status === 507) {
                    var title = (resp.meta.error_slug === 'file-size') ? 'Oops! This file is too large' : 'Wow! You have used up your file storage allotment';
                    TAPP.dialogs.upgrade_dialog(resp.meta.error_message, title, function () {
                        window.location = page_context.upgrade_storage_url;
                    });
                } else if (resp && xhr.status === 400) {
                    TAPP.dialogs.error_dialog(resp.meta.error_message);
                } else {
                    TAPP.dialogs.error_dialog();
                }
                this.upload_state.reject();
                this.reset_file_upload();
            }, this));

            this.current_upload.done($.proxy(function (resp) {
                var valid = this.validator === $.noop || this.validator(resp);
                if (valid) {
                    this.upload_state.resolve(resp);
                    this.on_upload_done(resp);
                } else {
                    this.upload_state.reject();
                    this.reset_file_upload();
                }
            }, this));
        },
        update_progress: function (percent_done) {
            this.on_progress(percent_done);
        }
    });

    window.TAPP.FileUploader = FileUploader;

    var FileUploadWidget = function (container, options) {
        this.container = container || $('body');
        this.init(options || {});
    };

    $.extend(FileUploadWidget.prototype, {
        init: function (opts) {
            var activator = this.activator = this.container.find('[data-attach-btn]');
            var file_input = this.container.find('[data-file-upload-input]');
            var preview_image_container = this.container.find('[data-image-preview-container]');
            this.name_preview = preview_image_container.find('[data-img-name]');
            this.upload_progress_cont = preview_image_container.find('[data-upload-progress]');
            this.upload_progress_bar = this.upload_progress_cont.find('.bar');
            this.remove_file = preview_image_container.find('[data-remove-attachment]');

            var defaults = {
                activator: activator,
                file_input: file_input,
                on_file: $.proxy(this.on_file, this),
                on_file_reset: $.proxy(this.on_file_reset, this),
                on_upload_start: $.proxy(this.on_upload_start, this),
                on_progress: $.proxy(this.on_progress, this),
                on_upload_done: $.proxy(this.on_upload_done, this),
                on_disallow: $.proxy(this.on_disallow, this),
                upload_on_change: true,
                upload_to: $.proxy(TAPP.appdotnet_api.file_create, TAPP.appdotnet_api),
                current_file_id: null,
                current_file_token: null,
                delete_on_removal: true,
                extra_data: [
                    ['type', 'net.app.alpha.attachment']
                ],
                allow: /image\/(gif|png|jpeg)/
            };

            var options = $.extend({}, defaults, opts);

            this.uploader = new TAPP.FileUploader(options);
            this.current_file_id = options.current_file_id;
            this.current_file_token = options.current_file_token;
            this.uploader.bind_events();
            this.remove_file.on('click', $.proxy(function () {
                if (options.delete_on_removal) {
                    TAPP.appdotnet_api.file_delete(this.current_file_id, this.current_file_token);
                }
                this.uploader.reset_file_upload();
            }, this));
        },

        on_disallow: function () {
            TAPP.dialogs.error_dialog('You can only attach images. The file you tried to attach was not an image.');
        },

        on_file: function (file, on_file_read) {
            this.file = file;
            this.container.trigger('file', [file, on_file_read]);
            this.upload_progress_cont.removeClass('hide');
            this.name_preview.find('[data-text]').text(file.name);
        },

        on_file_reset: function () {
            this.current_file_id = null;
            this.file = null;
            this.container.trigger('file_reset');
            this.name_preview.find('[data-text]').text('').removeClass('text-success');
            this.upload_progress_cont.addClass('hide').removeClass('plain');
            this.upload_progress_bar.css('width', '0%').removeClass('hide');
            this.remove_file.addClass('hide');
            this.activator.removeClass('hide');
        },

        on_upload_start: function () {
            this.upload_progress_cont.removeClass('hide');
            this.upload_progress_bar.css('width', '0%');
            this.activator.addClass('hide');
            this.container.trigger('upload_start');
        },

        on_progress: function (percent_done) {
            percent_done = Math.max(percent_done, 5);
            this.upload_progress_bar.css('width', percent_done + '%');
            this.container.trigger('progress', [percent_done]);
        },

        on_upload_done: function (resp) {
            this.current_file_id = resp.data.id;
            this.current_file_token = resp.data.file_token;
            this.upload_progress_cont.addClass('plain');
            this.upload_progress_bar.addClass('hide');
            this.remove_file.removeClass('hide');
            this.name_preview.find('[data-text]').addClass('text-success');
            this.container.trigger('upload_done', [resp]);
        }
    });

    window.TAPP.FileUploadWidget = FileUploadWidget;

}());