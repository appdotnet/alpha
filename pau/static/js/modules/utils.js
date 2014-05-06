/*global Modernizr:true */
(function (P) {
    var window_load = $.Deferred();

    $(window).on('load', function () {
        window_load.resolve();
    });

    /**
     * Stolen from: http://stackoverflow.com/questions/1184624/serialize-form-to-json-with-jquery
     */
    $.fn.serializeObject = function (coerce_bools_to_int) {
        var o = {};
        var a = this.serializeArray();
        $.each(a, function () {
            if (o[this.name] !== undefined) {
                if (!o[this.name].push) {
                    o[this.name] = [o[this.name]];
                }
                o[this.name].push((this.value === undefined) ? '': this.value);
            } else {
                o[this.name] = (this.value === undefined) ? '': this.value;
            }

            if (coerce_bools_to_int) {
                if (o[this.name] === 'on') {
                    o[this.name] = 1;
                }

                if (o[this.name] === 'off') {
                    o[this.name] = 0;
                }
            }

        });

        return o;
    };

    // stick item to the top when scrolling
    $.fn.affix = (function () {
        var win = $(window);
        var affixed_elements = [];
        var scroll_top = win.scrollTop();

        var check_item = function (item, index, list) {
            var is_stuck = item.el.attr('data-is-stuck') === 'true';
            var near_top = (scroll_top <= (item.start_top - item.offset));
            if (is_stuck && near_top) {
                item.el.removeClass('stuck');
                item.el.attr('data-is-stuck', 'false');
            }

            if (!is_stuck && !near_top) {
                item.el.addClass('stuck');
                item.el.attr('data-is-stuck', 'true');
            }
        };

        var on_scroll = function () {
            scroll_top = win.scrollTop();
            _.each(affixed_elements, check_item);
        };

        var scroll_attached = false;
        var attach_scroll = function () {
            win.on('scroll.affix', _.debounce(on_scroll, 10));
            scroll_attached = true;
        };

        var affix = function (offset) {
            var $this = $(this);
            if (!$this.length) {
                return this;
            }

            var start_offset_top = $this.attr('data-start-offset-top');
            if (typeof(start_offset_top) === 'undefined') {
                start_offset_top = $this.offset().top;
                $this.attr('data-start-offset-top', start_offset_top);
            }
            start_offset_top = parseInt(start_offset_top, 10);

            if (!scroll_attached) {
                attach_scroll();
            }

            affixed_elements.push({
                offset: offset,
                el: $this,
                start_top: start_offset_top
            });

            return this;
        };

        affix.unload = function () {
            affixed_elements = [];
            scroll_top = win.scrollTop();
            win.off('scroll.affix');
            scroll_attached = false;
        };

        return affix;

    }());

    _.mixin({
        chunks: function (data, chunk_size) {
            var lists = _.groupBy(data, function (a, b) {
                return Math.floor(b / chunk_size);
            });
            lists = _.toArray(lists);
            return lists;
        }
    });

    TAPP.utils = {
        intcomma: function (str) {
            str = "" + str;
            // positive integers only, no decimals, no negative numbers
            return str.replace(/(\d)(?=(\d\d\d)+(?!\d))/g, "$1,");
        },
        show_form_errors: function (form, form_errors) {
            $.each(form_errors, function (key, val) {
                var field = form.find('.field-' + key);
                field.addClass('bad');
                var input = field.find('input,textarea');
                input.addClass('bad');

                var errors = '';
                $.each(val, function (i, error) {
                    errors += '<li>' + error + '</li>';
                });

                var error_container = field.find('ul.error');
                if (!error_container.length) {
                    input.after('<ul class="error"></ul>');
                    error_container = field.find('ul.error');
                }

                error_container.html(errors);
            });
        },
        show_new_form_errors: function (form, form_errors) {
            $.each(form_errors, function (key, val) {
                var field = form.find('.field-' + key);
                field.addClass('error');
                var input = field.find('input,textarea');
                var errors = '';
                $.each(val, function (i, error) {
                    errors += '<li>' + error + '</li>';
                });

                var error_container = field.find('ul.help-inline');
                if (!error_container.length) {
                    input.after('<ul class="help-inline"></ul>');
                    error_container = field.find('ul.help-inline');
                }

                error_container.html(errors);
            });
        },
        clear_form_errors: function (form) {
            form.find('.field').each(function () {
                var field = $(this);
                field.removeClass('error');
                field.find('.help-inline').remove();
            });
        },
        is_touch: function () {
            return $('html').hasClass('touch');
        },
        is_widescreen: function () {
            return $('html').hasClass('breakpoint-widescreen');
        },
        is_phone: function () {
            return $('html').hasClass('breakpoint-phone');
        },
        handle_resize: function () {
            $(window).on('resize', _.debounce(Modernizr.test_media_queries, 50));
        },
        on_window_load: function (cb) {
            window_load.done(cb);
        },
        fit_to_box: function (w, h, max_w, max_h, expand) {
            expand = expand || false;
            // proportionately scale a box defined by (w,h) so that it fits within a box defined by (max_w, max_h)
            // by default, only scaling down is allowed, unless expand=True, in which case scaling up is allowed
            if ((w < max_w) && (h < max_h) && !expand) {
                return [w, h];
            }
            var largest_ratio = Math.max(w / max_w, h / max_h);
            var new_height = parseInt(h / largest_ratio, 10);
            var new_width = parseInt(w / largest_ratio, 10);
            return [new_width, new_height];
        },
        autofocus_polyfill: function () {
            if (!Modernizr.input.autofocus) {
                $('input[autofocus]').first().focus();
            }
        },
        emojify: function (html) {
            if (window.OSEmoji) {
                var frag = $('<div/>').append(html).get(0);
                window.OSEmoji.run(frag);
                return $(frag.childNodes);
            }
            return html;
        }
    };
}(TAPP));
