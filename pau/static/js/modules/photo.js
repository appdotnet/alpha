(function (P) {
    TAPP.photo = {
        init: function () {
            $('meta[name=viewport]').attr('content', 'width=device-width, initial-scale=1, maximum-scale=10');
            var center_and_resize = function () {
                var image_container = $('.image-container');
                var img = image_container.find('img');
                var img_width = img.attr('data-full-width');
                var img_height = img.attr('data-full-height');
                var max_height = image_container.height();
                var max_width = image_container.width();

                var dims = TAPP.utils.fit_to_box(img_width, img_height, max_width, max_height);
                var width = dims[0];
                var height = dims[1];

                img.hide();
                img.attr({
                    'width': width,
                    'height': height
                });
                img.css({
                    'margin-top': -1 * height / 2,
                    'margin-left': -1 * width / 2
                    // top 50% and left 50% set in css
                });
                img.show();
            };

            var img = $('.image-container img');
            var img_loaded = false;
            var loader = $('.loader');
            setTimeout(function () {
                // add a little delay before showing the spinner so it doesn't pop up all the time
                if (!img_loaded) {
                    loader.show();
                }
            }, 250);

            center_and_resize();
            img.imagesLoaded().done(function () {
                img_loaded = true;
                img.addClass('first-load');
                loader.hide();
            });
            $(window).tapp_on('resize', _.debounce(function () {
                center_and_resize();
            }, 50));

            $('.image-container').tapp_on('click', function () {
                $('[data-post-container]').toggle();
            });
        }
    };
}(TAPP));
