import json

from django.http import HttpResponse

from pau import bridge

PASS_THROUGH_HEADERS = (
    ('CONTENT_TYPE', 'Content-Type'),
    ('HTTP_X_ADN_MIGRATION_OVERRIDES', 'X-Adn-Migration-Overrides'),
)


def ajax_api_proxy(request, path, *args, **kwargs):
    data = request.POST
    if request.META.get('CONTENT_TYPE', None) == 'application/json':

        try:
            data = json.loads(request.body)
        except:
            pass

    headers = {}

    for dj_header, header in PASS_THROUGH_HEADERS:
        if dj_header in request.META:
            headers[header] = request.META[dj_header]
    path = '/' + path
    resp = bridge.api.call_api(request, path, params=request.GET, data=data, method=request.method, headers=headers)

    return HttpResponse(json.dumps(resp), content_type="application/json", status=resp['meta']['code'])
