(function () {

    var Autocomplete = {
        init: function () {
            var search_form = $('[data-search-bar-form]');
            var search_bar = search_form.find("input.search-bar-input");

            if (search_bar.length === 0) {
                return;
            }

            search_bar.typeahead([{
                name: 'universal',
                template: function (datum) {
                    return datum.html;
                },
                remote: {
                    url: page_context.autocomplete_url + '?q=%QUERY',
                    filter: function (resp) {
                        return resp.response;
                    },
                    dataType: 'jsonp'
                }
            }]);

            search_bar.tapp_on('typeahead:selected', function (e, datum) {
                if (datum.search !== undefined) {
                    $.ajax({
                        url: page_context.search_log_url,
                        dataType: 'jsonp',
                        data: {
                            'search-data': datum.search
                        }
                    });
                }
                window.setTimeout(function () {
                    window.location = datum.url;
                }, 50);
            });

            search_bar.tapp_on('typeahead:autocomplete', function (e, datum) {
                search_form.submit();
            });

            search_bar.tapp_on('keypress', function (e) {
                if (e.which === 13) {
                    search_form.get(0).submit();
                }
            });

            search_form.find('[type="submit"]').tapp_on('click', function () {
                search_form.get(0).submit();
            });

        }
    };

    TAPP.autocomplete = Autocomplete;

}());
