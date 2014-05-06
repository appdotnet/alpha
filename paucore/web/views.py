from contextlib import contextmanager
import re
import collections
import json
import os

from django.views.generic import TemplateView
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.middleware.csrf import get_token

from paucore.utils.string import camelcase_to_underscore
from paucore.web.template import render_template_response


class ViewContext(dict):
    response = None
    status_code = 200

    def update_ctx(self, ctx_item):
        page_load_hooks = self.get('__js_page_load_hooks', [])

        if ctx_item:
            if '__js_page_load_hooks' in ctx_item:
                page_load_hooks.extend([h for h in ctx_item['__js_page_load_hooks'] if h not in page_load_hooks])
                del ctx_item['__js_page_load_hooks']

            self.update(ctx_item)

        self['__js_page_load_hooks'] = page_load_hooks


# This is based on the mxmlbase.web.template template_response decorator
# but since we don't use any kwargs except for extra_ctx there, that's all I'm porting to this object
class MMLTemplateView(TemplateView):
    page_title = None
    page_description = None
    no_cache = False
    minify_html = None
    extra_ctx = None
    # Setting the CSRF cookie by default has saved us from a lot of stupid bugs,
    # but sometimes we want to turn this off.
    set_csrf_token = True

    def populate_context(self, request, *args, **kwargs):
        self.view_ctx['page_title'] = self.view_ctx.get('page_title', self.page_title)
        self.view_ctx['page_description'] = self.view_ctx.get('page_description', self.page_description)

    def get(self, request, *args, **kwargs):
        # right now, I'm still feeling out how these pieces will be put together but the current simple migration path
        # is that populate_context is essentially the same interface as the views we currently have. As I figure out more
        # refactoring, this will change
        # right now, i'm calling update_ctx just so i can still return dicts from populate_context i used to
        self.populate_context(request, *args, **kwargs)

        if self.set_csrf_token:
            # Ensure a CSRF Cookie
            get_token(request)

        # If this has been set, we want to take this path even if it's [] so a pure falsey check won't work
        if self.view_ctx.response is not None:
            return self.view_ctx.response
        else:
            return render_template_response(request, self.view_ctx, self.template_name, no_cache=self.no_cache,
                                            minify_html=self.minify_html, extra_ctx=self.extra_ctx,
                                            status_code=self.view_ctx.status_code)

    def dispatch(self, request, *args, **kwargs):
        self.view_ctx = ViewContext()
        return super(MMLTemplateView, self).dispatch(request, *args, **kwargs)

    def json_error(self, response):
        response_dict = {
            'result': 'error',
            'response': response
        }

        return self.json_response(response_dict)

    def json_success(self, response):
        response_dict = {
            'result': 'ok',
            'response': response
        }

        return self.json_response(response_dict)

    def json_response(self, response_dict):
        return HttpResponse(json.dumps(response_dict), content_type='application/json')


# This is a separate class primarily because sometimes we don't
# want you to be able to POST things.
class MMLActionView(MMLTemplateView):
    ACTION_RE = re.compile(r'^action_[a-z0-9_]+$')

    def user_can_call(self, request, action):
        return True

    def post(self, request, *args, **kwargs):
        if 'action' in request.POST:
            action = 'action_%s' % request.POST['action'].strip()
            if self.ACTION_RE.match(action):
                action_callable = getattr(self, action, None)
                if action_callable and isinstance(action_callable, collections.Callable) and self.user_can_call(request, action):
                    self.populate_context(request, *args, **kwargs)
                    if isinstance(self.view_ctx.response, HttpResponse):
                        return self.view_ctx.response
                    else:
                        response = action_callable(request, request.POST, *args, **kwargs)
                        if isinstance(response, HttpResponse):
                            return response
                        else:
                            return render_template_response(request, self.view_ctx, self.template_name, no_cache=self.no_cache,
                                                            minify_html=self.minify_html, extra_ctx=self.extra_ctx)

        raise Http404()


class ResponseState(dict):
    """
    This class is instantiated per each web request to contain objects as the response is built up
    essentially a convenient container for any response objects until template context can be created
    """

    def __init__(self, request, *view_args, **view_kwargs):
        self.request = request
        self.view_args = view_args
        self.view_kwargs = view_kwargs
        self.GET = request.GET
        self.POST = request.POST
        self.META = request.META
        self.method = self.request.method.lower()

        if self.method in ('get', 'head', 'options'):
            self.DATA = self.GET
        elif self.method in ('post', 'put', 'patch', 'delete'):
            self.DATA = self.POST

        get_token(self.request)

    def __setattr__(self, name, val):
        return self.__setitem__(name, val)

    def __getattr__(self, name):
        try:
            return self.__getitem__(name)
        except KeyError:
            raise AttributeError(name)

    def get_data_or_404(self, name):
        val = self.DATA.get(name)
        if val is None:
            raise Http404()
        return val

    def int_data_or_404(self, name):
        val = self.get_data_or_404(name)
        try:
            val = int(val)
        except:
            raise Http404()
        return val

    def obj_data_or_404(self, name, model_class):
        pk = self.int_data_or_404(name)
        return model_class.objects.by_pk(pk, or_404=True)

    @property
    def omo_user(self):
        return self.request.omo_user

    @contextmanager
    def update_omo_user(self):
        from omo.models.users import User
        yield self.omo_user
        self.request.omo_user = User.objects.by_pk(self.omo_user.pk)


class EarlyReturn(Exception):
    """ use this if you are quitting out early to e.g. redirect the user or display an error case """

    def __init__(self, response, *args, **kwargs):
        # there's really no use for a message here since this exception is intended to be caught
        self.response = response
        args = ('Uncaught EarlyReturn Exception - did you call this outside dispatch?',)
        super(EarlyReturn, self).__init__(*args, **kwargs)


class ViewMiddleware(object):
    """
    just a basic interface for how these middlewares work
    you may modify view_inst.state or simply raise EarlyReturn
    this should be thought of as roughly the same as a django middleware but can be applied dynamically to Views
    """

    def process_pre_view(self, view_inst):
        pass

    def process_post_view(self, view_inst):
        pass

    def process_pre_template(self, view_inst):
        pass

    def process_post_template(self, view_inst):
        pass


# TODO come up with real name of this thing
# XXX consider not even inheriting from django at all
class StatesAndHooksView(TemplateView):
    """
    new iteration on template-based responses. maintain your state on self.state at pre-defined hooks, saving template rendering for last
    """
    inherited_class_name = 'View'  # override this in abstract views that inherit from here that change their descendant names
    template_dir = ''  # override this in abstract views to set the root template directories
    no_cache = False
    minify_html = None
    ACTION_RE = re.compile(r'^action_[a-z0-9_]+$')

    def __init__(self, *args, **kwargs):
        super(StatesAndHooksView, self).__init__(*args, **kwargs)
        self.view_middlewares = []

    def get_template_name(self, extension=None):
        """
        template names are automatically generated, so use this to find your class's template
        if you have run-time template selection, setting extension will allow you to select a different template
            (extension will be appended as e.g. _foo to your default template name)
        """
        base = camelcase_to_underscore(self.__class__.__name__.rsplit(self.inherited_class_name, 1)[0])
        return os.path.join(self.template_dir, '%s%s.html' % (base, ('_%s' % extension) if extension else ''))

    # let's be slightly cranky about these being missing. add a page_title and page_description, yo!
    @property
    def page_title(self):
        raise NotImplementedError

    @property
    def page_description(self):
        raise NotImplementedError

    def dispatch(self, request, *args, **kwargs):
        self.state = ResponseState(request, *args, **kwargs)
        self.template_name = self.get_template_name()
        self.state.page_title = self.page_title
        self.state.page_description = self.page_description
        self.state.response_type = 'html'

        try:
            for view_middleware in self.view_middlewares:
                view_middleware.process_pre_view(self)

            self.init_hook()

            # somewhat disingenuous - call super on dispatch. this is just to let it resolve method names the way it do
            #   we aren't actually looking for any kind of full response object yet, just to build self.state (different return type)
            super(StatesAndHooksView, self).dispatch(request)

            for view_middleware in self.view_middlewares:
                view_middleware.process_post_view(self)

            if self.state.response_type == 'html':
                # here we equate 'html' and 'template'
                self.state.template_ctx = {}
                for view_middleware in self.view_middlewares:
                    view_middleware.process_pre_template(self)
                self.template_hook()
                for view_middleware in self.view_middlewares:
                    view_middleware.process_post_template(self)
                response = render_template_response(request, self.state.template_ctx, self.template_name, no_cache=self.no_cache,
                                                    minify_html=self.minify_html)

                return response
            elif self.state.response_type == 'json':
                self.state.json_ctx = {}
                self.json_hook()
                return HttpResponse(json.dumps(self.state.json_ctx), content_type='application/json')
            elif self.state.response_type == 'redirect':
                return HttpResponseRedirect(self.state.redirect_url)
            else:
                raise Exception('Unrecognized response_type %s', self.state.response_type)

        except EarlyReturn, er:
            return er.response

    def get(self, _request):
        self.GET_request_hook()

    def post(self, _request):
        self.POST_request_hook()

    def options(self, request, *args, **kwargs):
        response = super(StatesAndHooksView, self).options(request, *args, **kwargs)
        raise EarlyReturn(response)

    def http_method_not_allowed(self, request, *args, **kwargs):
        response = super(StatesAndHooksView, self).http_method_not_allowed(request, *args, **kwargs)
        raise EarlyReturn(response)

    def copy_state_to_template(self, **keys_defaults):
        """
        often, we will want to take a bunch of keys out of self.state and put them into self.state.template_ctx
            that's cool, but let's do it very explicitly
        """
        for key, default in keys_defaults.iteritems():
            self.state.template_ctx[key] = self.state.get(key, default)

    # ------- override some/all of below -------

    def init_hook(self):
        pass

    def GET_request_hook(self):
        pass

    def POST_request_hook(self):
        if 'action' in self.state.POST:
            action = 'action_%s' % self.state.POST['action'].strip()
            if self.ACTION_RE.match(action):
                action_callable = getattr(self, action, None)
                if action_callable and isinstance(action_callable, collections.Callable):
                    self.pre_action_hook()
                    action_callable()
                    self.post_action_hook()
                    return

        raise Http404()

    def pre_action_hook(self):
        pass

    def post_action_hook(self):
        pass

    def template_hook(self):
        self.state.template_ctx['page_title'] = self.state.page_title
        self.state.template_ctx['page_description'] = self.state.page_description

    def json_hook(self):
        pass


class ViewMiddlewareTransitional(ViewMiddleware):
    """
    handy class to rework legacy view mixins to be hybrids (mixins and ViewMiddlewares) assuming the mixin fills some stuff into template ctx
    """

    def process_post_template(self, view_inst):
        self.update_template_ctx(view_inst.request, view_inst.state.template_ctx)

    def update_template_ctx(self, request, ctx):
        pass

    def populate_context(self, request, *args, **kwargs):
        super(ViewMiddlewareTransitional, self).populate_context(request, *args, **kwargs)
        self.update_template_ctx(request, self.view_ctx)
