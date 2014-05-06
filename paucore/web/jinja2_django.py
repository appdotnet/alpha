"""
See http://docs.djangoproject.com/en/dev/ref/templates/api/#using-an-alternative-template-language

Use:
 * {{ url_for('view_name') }} instead of {% url view_name %},
 * <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
   instead of {% csrf_token %}.

"""
import simplejson as json
import logging

from django.template.loader import BaseLoader
from django.template import TemplateDoesNotExist
from django.conf import settings
from django.template.defaultfilters import escapejs, pluralize, urlencode
from django.contrib.humanize.templatetags.humanize import intcomma
from django.test import signals
import jinja2

from paucore.utils.htmlgen import render_etree, render_presenters
from paucore.utils.string import possessive, string_to_css_class, do_filesizeformat


JSCONTEXT_KEY_PREFIX = '__js_'
JSCONTEXT_KEY_PREFIX_LEN = len(JSCONTEXT_KEY_PREFIX)


logger = logging.getLogger(__name__)


def datetimeformat(value, format='%H:%M / %d-%m-%Y'):
    return value.strftime(format)


def filter_none(val):
    return '' if val is None else val


def mxml_safe(value):
    # jinja2.Environment finalize doesn't work with safe, so make a wrapper for this common pattern
    return jinja2.Markup(filter_none(value))


def guess_autoescape(template_name):
    if template_name is None or '.' not in template_name:
        return False
    ext = template_name.rsplit('.', 1)[1]
    return ext in ('html', 'xml')


class Template(jinja2.Template):

    def render(self, context):
        # flatten the Django Context into a single dictionary.
        # This code is duplicated in the get_macro_module function, kind of.
        # If you find bugs here, you may want to update that function too.
        context_dict = {}

        for d in context.dicts:
            context_dict.update(d)

        jscontext = {}

        for k, v in context_dict.iteritems():
            if k.startswith(JSCONTEXT_KEY_PREFIX):
                jscontext[k[JSCONTEXT_KEY_PREFIX_LEN:]] = v

        context_dict['page_context'] = json.dumps(jscontext, separators=(',', ':'))

        if 'page_title' in context_dict and context_dict['page_title'] is None:
            logger.warning("SET A PAGE TITLE FOR %s", self)
            if settings.DEBUG:
                raise Exception("SET A PAGE TITLE!!!!")

        # This is useful for unit tests, so we can see the contexts used.
        signals.template_rendered.send(sender=self, template=self, context=context_dict)

        return super(Template, self).render(context_dict)


class Loader(BaseLoader):
    is_usable = True

    def __init__(self, *args, **kwargs):
        choices = []
        template_modules = {}
        for pkg in getattr(settings, 'JINJA2_TEMPLATE_PACKAGES', []):
            pkg_prefix = pkg.split('.')[-1]
            template_modules[pkg_prefix] = jinja2.PackageLoader(pkg, package_path='templates-jinja2')

        choices.append(jinja2.PrefixLoader(template_modules))
        choices.append(jinja2.FileSystemLoader(getattr(settings, 'JINJA2_TEMPLATE_DIRS', [])))

        loader = jinja2.ChoiceLoader(choices)

        extensions = (
            'jinja2.ext.with_',
            'jinja2.ext.i18n',
            'jinja2.ext.autoescape',
        )

        if settings.DEBUG:
            cache_size = 50
        else:
            cache_size = -1

        env = jinja2.Environment(autoescape=guess_autoescape, trim_blocks=True, loader=loader, extensions=extensions,
                                 cache_size=cache_size, auto_reload=settings.DEBUG, finalize=filter_none)

        env.template_class = Template
        env.filters['datetimeformat'] = datetimeformat
        env.filters['filesizeformat'] = do_filesizeformat
        env.filters['escapejs'] = escapejs
        env.filters['urlencode'] = urlencode
        env.filters['intcomma'] = intcomma
        env.filters['render_etree'] = render_etree
        env.filters['render_presenters'] = render_presenters
        env.filters['possessive'] = possessive
        env.filters['string_to_css_class'] = string_to_css_class
        env.filters['pluralize'] = pluralize
        env.filters['safe'] = mxml_safe

        env.install_null_translations()

        # These are available to all templates.
        env.globals['settings'] = settings
        env.globals['MEDIA_URL'] = settings.MEDIA_URL
        env.globals['DEBUG'] = settings.DEBUG
        env.globals['ENVIRONMENT'] = getattr(settings, 'ENVIRONMENT', 'unknown')
        env.globals['BUILD_INFO'] = '%s host: %s' % (getattr(settings, 'BUILD_INFO', 'unknown'),
                                                     getattr(settings, 'SERVER_HOSTNAME', 'unknown'))

        self.env = env

        super(Loader, self).__init__(*args, **kwargs)

    def load_template(self, template_name, template_dirs=None):
        try:
            template = self.env.get_template(template_name)
        except jinja2.TemplateNotFound:
            raise TemplateDoesNotExist(template_name)
        return template, template.filename
