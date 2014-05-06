/* globals Sentry:true */
/* Polyfill $.browser */
(function () {
    if (window.TAPP && window.TAPP.initialized) {
        // We have already run the intialization code
        return;
    }

    window.TAPP = window.TAPP || {};
    window.TAPP.initialized = true;

    // Limit scope pollution from any deprecated API
    (function () {

        var matched, browser;

        // Use of jQuery.browser is frowned upon.
        // More details: http://api.jquery.com/jQuery.browser
        // jQuery.uaMatch maintained for back-compat
        jQuery.uaMatch = function (ua) {
            ua = ua.toLowerCase();

            var match = /(chrome)[ \/]([\w.]+)/.exec(ua) ||
                /(webkit)[ \/]([\w.]+)/.exec(ua) ||
                /(opera)(?:.*version|)[ \/]([\w.]+)/.exec(ua) ||
                /(msie) ([\w.]+)/.exec(ua) ||
                ua.indexOf("compatible") < 0 && /(mozilla)(?:.*? rv:([\w.]+)|)/.exec(ua) ||
                [];

            return {
                browser: match[1] || "",
                version: match[2] || "0"
            };
        };

        matched = jQuery.uaMatch(navigator.userAgent);
        browser = {};

        if (matched.browser) {
            browser[matched.browser] = true;
            browser.version = matched.version;
        }

        // Chrome is Webkit, but Webkit is also Safari.
        if (browser.chrome) {
            browser.webkit = true;
        } else if (browser.webkit) {
            browser.safari = true;
        }

        jQuery.browser = browser;

        jQuery.sub = function () {
            function jQuerySub(selector, context) {
                return new jQuerySub.fn.init(selector, context);
            }
            jQuery.extend(true, jQuerySub, this);
            jQuerySub.superclass = this;
            jQuerySub.fn = jQuerySub.prototype = this();
            jQuerySub.fn.constructor = jQuerySub;
            jQuerySub.sub = this.sub;
            jQuerySub.fn.init = function init(selector, context) {
                if (context && context instanceof jQuery && !(context instanceof jQuerySub)) {
                    context = jQuerySub(context);
                }

                return jQuery.fn.init.call(this, selector, context, rootjQuerySub);
            };
            jQuerySub.fn.init.prototype = jQuerySub.fn;
            var rootjQuerySub = jQuerySub(document);
            return jQuerySub;
        };

    })();

    // If we accidentally leave a console.log in our code don't kill everything
    if (typeof(window.console) === "undefined") {
        window.console = {
            log: function () {
                return true;
            }
        };
    }

    $._ajax = $.ajax;

    $.ajax = function (conf, ajaxSettings) {
        var success = conf.success;

        conf.success = function (data, textStatus, jqXHR) {
            var result = (data && data.result) ? data.result : null,
                value = (data && data.value) ? data.value : 'ajax failed',
                text = (data && data.text) ? data.text : 'ajax failed';

            if (result && result !== "ok") {
                if (this.error) {
                    this.error(jqXHR, value, text);
                }
                return;
            }
            if (success) {
                success.apply(this, [data, textStatus, jqXHR]);
            }
        };

        return $._ajax(conf, ajaxSettings);
    };


    // This gets used for a nav to target ie 9
    (function () {

        var getInternetExplorerVersion = function () {
            // Returns the version of Internet Explorer or a -1
            // (indicating the use of another browser).
            var rv = -1; // Return value assumes failure.
            if (navigator.appName === 'Microsoft Internet Explorer') {
                var ua = navigator.userAgent;
                var re  = /MSIE ([0-9]{1,}[\.0-9]{0,})/;
                if (re.exec(ua) !== null) {
                    rv = parseFloat(RegExp.$1);
                }
            }

            return rv;
        };

        var ie_version = getInternetExplorerVersion();
        if (ie_version !== -1) {
            ie_version = ('' + ie_version).replace(/\./g, '_');
            $('html').addClass('ie v' + ie_version + '_0');
        }

    }());


    /* set up the page_context, but allow use to refersh it in the case of pjax */
    window.refresh_page_context = function (pjax_context) {
        var new_page_context = document.getElementById('adn-page-context');
        if (new_page_context) {
            var json = new_page_context.getAttribute('data-adn-page-context');
            window.page_context = JSON.parse(json);
            //new_page_context.parentNode.removeChild(new_page_context);
        }
        window.pjax_context = pjax_context || {};

    };
    window.refresh_page_context();

    /* unsetable functions */
    (function () {
        var event_handles = [];
        var subscribe_handles = [];
        var intervals = [];

        $.fn.tapp_on = function (types, selector, data, fn) {
            event_handles.push([this, types, selector]);
            return this.on(types, selector, data, fn);
        };

        $.tapp_subscribe = function (topic, callback) {
            var subscribe_handle = $.subscribe(topic, callback);
            subscribe_handles.push(subscribe_handle);
            return subscribe_handle;
        };

        TAPP.setInterval = function (func, time) {
            var interval = setInterval(func, time);
            intervals.push(interval);
            return interval;
        };

        TAPP.clearInterval = function (key) {
            $.map(intervals, function (val, i) {
                if (key === val) {
                    return null;
                }
                return val;
            });
        };

        TAPP.clear_event_handles = function () {
            $.each(event_handles, function (i, val) {
                $(val[0]).off(val[1], val[2]);
            });
        };

        TAPP.clear_subscribe_handles = function () {
            $.each(subscribe_handles, function (i, val) {
                $.unsubscribe(val);
            });
        };

        TAPP.clear_intervals = function () {
            $.each(intervals, function () {
                clearInterval(this);
            });
        };


        TAPP.unload = function () {
            TAPP.clear_event_handles();
            TAPP.clear_subscribe_handles();
            TAPP.clear_intervals();
        };

        TAPP.lock_up = function (button, event_type) {
            event_type = event_type || 'click';

            var handler = function (e) {
                e.preventDefault();
                e.stopImmediatePropagation();
            };

            var event_handle = button.on(event_type, handler);

            return function () {
                // Wait until the next tick for this to happen.
                setTimeout(function () {
                    button.off(event_type, handler);
                }, 0);
            };
        };

        // A generic replacement for the class method in TAPP.Module
        TAPP.register_post_load_hooks = function (functions, proxy) {
            $.each(functions, function (ev, func) {
                $.subscribe(ev, $.proxy(func, proxy));
            });
        };

        TAPP.conditional_bindings = (function () {
            var bindings = [];

            var add = function (selector, fn) {
                bindings.push([selector, fn]);
            };
            var all = function () {
                return bindings;
            };
            return {
                add: add,
                all: all
            };
        }());
    }());

    (function () {
        /*
        waitForFuncs: use this to call the same function multiple times and wait until all function
        calls are complete before executing the callback.

        Example:
            var args_queue = [
                [1, 2],
                [2, 3],
                [4, 5],
            ];

            var add = function(a, b, callback) {
                console.log(a, b, a+b);
                callback(a + b);
            };

            var done = function(){
                console.log('all done');
            };

            $.waitForFuncs(args_queue, add, done);
            > 1, 2, 3
            > 2, 3, 5
            > 4, 5, 9
            > all done

        */
        $.waitForFuncs = function (args_queue, func, callback) {
            var deferreds = [];
            $.each(args_queue, function (idx, args) {
                var event_deferred = $.Deferred();
                deferreds.push(event_deferred);

                args.push(function () {
                    event_deferred.resolve();
                });

                func.apply(this, args);
            });

            $.when.apply(this, deferreds).done(callback);
        };
    }());

    // Mobile safari fix for 6.1
    $(document).ajaxSend(function (event, xhr, settings) {
        if (settings.type === 'POST') {
            xhr.setRequestHeader("Cache-Control", "no-cache");
        }
    });

    // For FB related code
    TAPP.FB_INIT_DEFERRED = $.Deferred();

    // Once the DOM is ready go...
    $(document).ready(function () {
        var do_page_hooks = function () {
            var page_load_hooks = page_context.page_load_hooks;
            if (page_load_hooks) {
                if (!$.isArray(page_context.page_load_hooks)) {
                    page_load_hooks = [page_load_hooks];
                }
                // If the hook has a . in it then it references a function inside TAPP
                // otherwise it is just an event that should be published
                $.each(page_context.page_load_hooks, function (i, action) {
                    if (action.indexOf('.') !== -1) {
                        var func_path = action.split('.');
                        var func_ref = TAPP;
                        var context;
                        $.each(func_path, function (i, attr) {
                            context = func_ref;
                            func_ref = func_ref[attr];
                        });

                        if ($.isFunction(func_ref)) {
                            func_ref.call(context);
                        }
                    } else {
                        $.publish(action);
                    }
                });
            }
            $.publish('js_init_done');
        };

        do_page_hooks();

        $(window).on('pjax:start', function () {
            TAPP.unload();
            $.each(TAPP, function () {
                if (this && this.unload) {
                    this.unload();
                }
            });
        });

        $(window).on('pjax:end', function () {
            do_page_hooks();
        });
    });
})();

