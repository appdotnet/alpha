from functools import wraps

from django.http import HttpResponse
from django.template.loader import render_to_string, get_template
from django.template import RequestContext
from slimmer import slimmer

from paucore.utils.data import is_seq_not_string
from paucore.stats.statsd_client import graphite_timer


def minify(html):
    "Convenience method."
    if isinstance(html, unicode):
        html = html.encode('utf-8')

    return slimmer.html_slimmer(html)


def render_template_string(request, ctx, template, minify_html=None, extra_ctx=None):
    with graphite_timer('jinja2.render_template_string'):
        if minify_html is None:
            minify_html = template.endswith('.html')

        if extra_ctx:
            if not is_seq_not_string(extra_ctx):
                extra_ctx = [extra_ctx]

            new_ctx = {}
            page_load_hooks = ctx.get('__js_page_load_hooks', [])

            for ctx_callable in extra_ctx:
                ctx_item = ctx_callable(request)
                if ctx_item:
                    if '__js_page_load_hooks' in ctx_item:
                        page_load_hooks.extend(ctx_item['__js_page_load_hooks'])
                        del ctx_item['__js_page_load_hooks']
                        new_ctx.update(ctx_item)

            new_ctx.update(ctx)
            new_ctx['__js_page_load_hooks'] = page_load_hooks

            ctx = new_ctx

        with graphite_timer('jinja2.render_to_string'):
            output = render_to_string(template, ctx, context_instance=RequestContext(request))

        if isinstance(output, unicode):
            output = output.encode('utf-8')

        if ctx and ctx.get('__no_minify'):
            minify_html = False

        if minify_html:
            with graphite_timer('jinja2.minify_html'):
                output = slimmer.html_slimmer(output)

        return output


def get_macro_module(request, ctx, template):
    """Fetch a module that represents a template for the purpose of rendering individual macros as snippets."""
    ctx = ctx or {}

    t = get_template(template)
    if hasattr(t, 'make_module'):
        context_instance = RequestContext(request)
        context_instance.update(ctx)

        flat_dict = {}

        for d in context_instance.dicts:
            flat_dict.update(d)

        return t.make_module(t.new_context(flat_dict))
    else:
        raise Exception('get_macro_module only works for Jinja2 templates')


def render_template_response(request, ctx, template, no_cache=False, minify_html=None, extra_ctx=None, status_code=200):
    response = HttpResponse(render_template_string(request, ctx, template, minify_html, extra_ctx), status=status_code)

    if no_cache:
        response['Pragma'] = 'no-cache'
        response['Cache-Control'] = 'no-cache, must-revalidate'

    return response


def template_response(template, no_cache=False, minify_html=None, extra_ctx=None):

    def render_template_decorator(view):

        @wraps(view)
        def inner(request, *a, **kw):
            ctx = view(request, *a, **kw)

            if isinstance(ctx, HttpResponse):
                return ctx
            else:
                return render_template_response(request, ctx, template, no_cache=no_cache, minify_html=minify_html,
                                                extra_ctx=extra_ctx)

        return inner
    return render_template_decorator
