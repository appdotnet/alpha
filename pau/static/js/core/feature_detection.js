/*global Modernizr:true */
(function () {
    var doc_element = document.documentElement;

    var queries = window.TAPP_MEDIA_QUERIES = {
        phone: "(max-width: 700px)",
        tablet: "(min-width: 701px) and (max-width: 1151px)",
        widescreen: "(min-width: 1152px)",
        retina: "only screen and (-webkit-min-device-pixel-ratio : 2)",
        height_large: "(min-height: 1200px)",
        height_medium: "(min-height: 950px) and (max-height: 1199px)",
        height_small: "(min-height: 600px) and (max-height: 949px)",
        height_mini: "(max-height: 599px)",
        height_extra_mini: "(max-height: 320px)"
    };

    var makeTest = function (query) {
            return function () {
                return Modernizr.mq(query);
            };
        };

    // remove the default state
    doc_element.className = doc_element.className.replace('breakpoint-phone', '');
    Modernizr.test_media_queries = function () {
        for (var name in queries) {
            Modernizr.addTest('breakpoint-' + name, makeTest(queries[name]));
        }
    };

    Modernizr.test_media_queries();

    // from https://github.com/Modernizr/Modernizr/blob/master/feature-detects/css/checked.js
    Modernizr.test_checked_selector = function () {
        Modernizr.addTest('checked', function () {
            return Modernizr.testStyles('#modernizr input {width:100px} #modernizr :checked {width:200px;display:block}', function (elem, rule) {
                var cb = document.createElement('input');
                cb.setAttribute("type", "checkbox");
                cb.setAttribute("checked", "checked");
                elem.appendChild(cb);
                return cb.offsetWidth === 200;
            });
        });
    };

    Modernizr.test_checked_selector();

}());