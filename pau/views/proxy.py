import json

from django.http import HttpResponse

from pau import bridge

PASS_THROUGH_HEADERS = (
    ('HTTP_X_ADN_MIGRATION_OVERRIDES', 'X-Adn-Migration-Overrides'),
)


def ajax_api_proxy(request, path, *args, **kwargs):
    data = request.POST
    post_type = 'form_data'  # default to form data unless the client sent us json

    if request.META.get('CONTENT_TYPE', None) == 'application/json':

        try:
            data = json.loads(request.body)
            post_type = 'json'
        except:
            pass

    headers = {}
    files = {}

    for file_slug, f in request.FILES.iteritems():
        files[file_slug] = (f.name, f, f.content_type)

    for dj_header, header in PASS_THROUGH_HEADERS:
        if dj_header in request.META:
            headers[header] = request.META[dj_header]

    path = '/' + path

    resp = bridge.api.call_api(request, path, params=request.GET, data=data, method=request.method, headers=headers,
                               post_type=post_type, files=files)

    return HttpResponse(json.dumps(resp), content_type="application/json", status=resp['meta']['code'])
