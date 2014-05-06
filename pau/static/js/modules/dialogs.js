/**
 *  Creating a dialog, this code is for you.
 */

(function () {
    var default_dialog_conf = {
            backdrop: false,
            zIndex: 10000,
            buttons: {
                "Close": function () {
                    $(this).modal("close");
                }
            }
        };

    var create_bootstrap_dialog = function (header, body, footer) {
        header = $("<div/>").addClass('modal-header').html(header);
        body = $("<div/>").addClass("modal-body").html(body);
        footer = $("<div/>").addClass("modal-footer btn-group-spaced").html(footer);
        var modal = $("<div/>").addClass('modal').append(header).append(body).append(footer);
        modal.addClass('hide').appendTo($('body'));

        return $(modal);
    };

    var button_builder = function (buttons) {

        if (!buttons) {
            return null;
        }

        var button_dom = $('<div/>');

        $.each(buttons, function (button_text, button_conf) {
            var text = button_conf.text || button_text;
            var classes = button_conf['class'] || 'btn btn-small';
            var attrs = button_conf.attrs || {};
            var data = button_conf.data || {};
            var onclick = button_conf.click || $.noop();
            var html = button_conf.html;

            var button = $('<button/>')
                .text(text)
                .addClass(classes)
                .on('click', onclick)
                .data(data);

            if (html) {
                button.html(html);
            }

            $.each(attrs, function (key, val) {
                button.attr(key, val);
            });

            button_dom.append(button);

        });

        return button_dom;
    };

    var build_dialog = function (dialog_body, extra_conf) {
        /*
        *  overloading this fist argument here. It can be a string, or a jquery element.
        */
        if (typeof(dialog_body) !== 'string') {
            dialog_body = dialog_body.html();
        }

        var title = extra_conf.title || '';

        var footer = (extra_conf.buttons) ? button_builder(extra_conf.buttons) : extra_conf.footer || '';

        var dialog_conf = $.extend({}, default_dialog_conf, extra_conf);

        var dialog = create_bootstrap_dialog(title, dialog_body, footer);
        dialog.addClass(dialog_conf.modal_classes);

        dialog.modal(dialog_conf);

        return dialog;
    };

    TAPP.dialogs = {
        markup_dialog: function (element, extra_conf) {
            return build_dialog(element, extra_conf);
        },
        error_dialog: function (message, callback, extra_conf) {
            var dialog;

            message = message || 'Something is wrong with the server. Please wait a moment and try again.';

            var dialog_conf = $.extend({}, {
                title: "<h3>An error occurred<h3>",
                modal_classes: 'error-dialog',
                buttons: {
                    Ok: {
                        click: function () {
                            dialog.modal("hide");
                            dialog.remove();
                            if (callback) {
                                callback();
                            }
                        }
                    }
                }
            }, extra_conf);

            dialog = build_dialog(message, dialog_conf);

            dialog.modal('show');
            return dialog;
        },
        confirm_dialog: function (trigger_el, trigger_event, message, title, dialog_class, the_buttons) {
            title = title || "<h3>Are you sure?</h3>";
            dialog_class = (dialog_class || '') + ' confirmation-dialog';
            // Create and insert the "confirm" dialog box into the dom
            var trigger = $(trigger_el);

            // when the event happens, show the confirm dialog box
            var show_dialog = function (e) {
                e.preventDefault();
                e.stopImmediatePropagation();

                var my_dialog;

                var el = $(this),
                    buttons = the_buttons || {
                        "Cancel": {
                            click: function () {
                                my_dialog.modal("hide");
                            },
                            'class': 'btn btn-small'
                        },
                        "Continue": {
                            click: function () {
                                // if they click ok, do the trigger element's original action
                                el.unbind(e);
                                el.trigger($.Event(trigger_event));
                                my_dialog.modal("hide");
                            },
                            text: "Continue",
                            'class': 'btn btn-primary btn-small'
                        }
                    };

                if (!el.data('dialog-init')) {
                    var dialog_conf = {
                            title: '<h3>' + title + '</h3>',
                            modal_classes: dialog_class,
                            buttons: buttons
                        };
                    my_dialog = build_dialog(message, dialog_conf);
                    el.data('dialog-init', my_dialog);
                } else {
                    my_dialog = el.data('dialog-init');
                }
                my_dialog.modal('show');

                return false;
            };

            trigger.bind(trigger_event, show_dialog);
        },
        deferred_confirm_dialog: function (message, title, dialog_class, the_buttons) {
            var deferred = $.Deferred();
            title = title || "<h3>Are you sure?</h3>";
            dialog_class = (dialog_class || '') + ' confirmation-dialog';

            var my_dialog;

            var buttons = the_buttons || {
                    "Cancel": {
                        click: function () {
                            my_dialog.modal("hide");
                            my_dialog.remove();
                            deferred.reject();
                        },
                        'class': 'btn btn-small'
                    },
                    "Continue": {
                        click: function () {
                            my_dialog.modal("hide");
                            my_dialog.remove();
                            deferred.resolve();
                        },
                        text: "Continue",
                        'class': 'btn btn-primary btn-small'
                    }
                };

            var dialog_conf = {
                    title: '<h3>' + title + '</h3>',
                    modal_classes: dialog_class,
                    buttons: buttons
                };
            my_dialog = build_dialog(message, dialog_conf);
            my_dialog.modal('show');

            return deferred.promise();
        },
        upgrade_dialog: function (reason, title, success) {
            title = '<h3>' + (title || 'Upgrade To Get More') + '</h3>';
            var my_dialog;
            var close_dialog = function () {
                my_dialog.modal("hide");
                my_dialog.remove();
            };

            var dialog_conf = {
                title: title,
                modal_classes: 'upgrade-dialog',
                backdrop: true,
                buttons: {
                    'Close': {
                        click: close_dialog,
                        'class': 'pull-left btn'
                    },
                    'Upgrade': {
                        click: function () {
                            close_dialog();
                            success();
                        },
                        'class': 'btn btn-success'
                    }

                }
            };
            var message = '<p>' + reason + '</p>';

            my_dialog = build_dialog(message, dialog_conf);

            return my_dialog;
        }
    };

    TAPP.register_post_load_hooks({
        'confirm_dialog': TAPP.dialogs.confirm_dialog,
        'error_dialog': TAPP.dialogs.error_dialog
    }, TAPP.dialogs);

}());
