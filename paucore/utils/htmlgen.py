import logging
import re
import simplejson as json
import traceback
import sys

from functools import partial

from lxml.builder import ElementMaker
import lxml.html
from lxml.etree import Entity
from lxml.html import html_parser, HtmlElement
import jinja2

from paucore.utils.data import is_seq_not_string


logger = logging.getLogger(__name__)
if sys.maxunicode == 65535:
    # Heroku seems to use a narrow python build
    IMPROPER_HTML_ENCODING = re.compile(ur'[^\u0009\u000A\u000D\u0020-\uD7FF\uE000-\uFFFD]')
else:
    IMPROPER_HTML_ENCODING = re.compile(ur'[^\u0009\u000A\u000D\u0020-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]')


def _flatten_classes(classes):
    return set((' '.join(classes)).split(' '))


def _format_classes(class_set):
    return ' '.join(class_set)


def render_etree(tree):
    # HtmlElement is a seq, but we want to treat seqs of HtmlElements differently than HtmlElements
    # XXX verify that this is a list of HtmlElements? we'll see after we audit redner_etree_to_string
    if tree is not None and is_seq_not_string(tree) and not isinstance(tree, HtmlElement):
        return jinja2.Markup(''.join(map(render_etree_to_string, tree)))
    elif tree is not None and not isinstance(tree, jinja2.runtime.Undefined):
        # etrees evaluate to false, so we check is not None, but jinja2.runtime.Undefined could get passed in here
        return jinja2.Markup(lxml.html.tostring(tree))
    elif isinstance(tree, basestring):
        return tree
    else:
        return ''


def html_from_string(s):
    html_str = ''
    if s:
        try:
            html_str = lxml.html.fromstring(s)
        except lxml.etree.ParserError:
            pass

    return html_str


def render_etree_to_string(tree):
    # 6/1/12 mthurman: if I don't see these log messages, then in render_etree i'm going to
    # filter(lambda t: isinstance(t, HtmlElement), tree) in the 1st clause
    # We really should only pass in an lxml etree here
    if tree is None:
        message = 'render_etree_to_string called with None object\n%s' % ''.join(traceback.format_stack())
        logger.error(message)
        return ''
    elif isinstance(tree, basestring):
        return tree
    else:
        return lxml.html.tostring(tree)


def render_presenters(presenters, wrapper=None, sep=None):
    # just checking if presenters doesn't work for HtmlElements, so check that separately--they don't need to go through present
    if isinstance(presenters, HtmlElement):
        return render_etree(presenters)
    elif presenters:
        trees = HtmlGen().present(presenters, wrapper, sep)
        return render_etree(trees)
    else:
        return ''


def extract_classes(attrs):
    class_ = attrs.pop('class_', ())
    if not is_seq_not_string(class_):
        class_ = (class_,)

    return (class_, attrs)


class MXMLGenericElementMixin(object):

    @property
    def classes(self):
        c = self.attrib.get('class', '').split(' ')
        return set(filter(None, c))

    def add_class(self, *args):
        new_classes = _flatten_classes(args)

        self.attrib['class'] = _format_classes(self.classes | new_classes)

        return self

    def remove_class(self, *args):
        rm_classes = _flatten_classes(args)

        self.attrib['class'] = _format_classes(self.classes - rm_classes)

        return self

    def data(self, key, value):
        self.attrib['data-%s' % key] = value

        return self


# It's just like Ruby! OMG. :(
HtmlElement.__bases__ += (MXMLGenericElementMixin,)


maker = ElementMaker(makeelement=html_parser.makeelement)
_cls_cache = {}


# TODO:
# Mark's thoughts about some of this:
# - making links/buttons is going to be such a common case we'll probably want a helper method in here for that
class HtmlGen(object):
    def __init__(self, maker=maker):
        super(HtmlGen, self).__init__()
        self.maker = maker

    def __getattr__(self, attr):
        return partial(self.el, attr)

    def el(self, tag, *args, **kwargs):
        canon_tag = tag.strip().lower()

        if canon_tag not in _cls_cache:
            _cls_cache[canon_tag] = getattr(self.maker, canon_tag)

        tag_cls = _cls_cache[canon_tag]

        (classes, kwargs) = extract_classes(kwargs)
        if classes:
            args = args + (self._classes(*classes),)

        style = kwargs.pop('style', None)
        if style:
            if isinstance(style, basestring):
                args = args + ({'style': style},)
            else:
                args = args + (self._style(**style),)

        data = kwargs.pop('data', None)
        if data:
            data_attributes = []

            for key, val in data.iteritems():
                encoded_val = val
                if val is None:
                    encoded_val = ''
                elif not isinstance(val, basestring):
                    encoded_val = json.dumps(val)
                data_attributes.append({
                    'data-%s' % (key): encoded_val
                })

            args = args + tuple(data_attributes)

        underscore_hacks = (
            ('for', 'for_'),  # labels, The for attribute in html will connect a label to an input
            ('type', 'type_'),  # inputs
            ('id', 'id_'),  # inputs
        )

        for correct, hack in underscore_hacks:
            value = kwargs.pop(hack, None)
            if value:
                args = args + ({correct: value}, )

        # if args contains any lists (not dicts), they have to be splated.
        # This allows presenter methods to return lists to html gen tags without have to wrap them in another element
        # I could probably make a special html.notag([...]) or somthing that would trigger this instead of types
        new_args = []
        for arg in args:
            if isinstance(arg, list):
                arg_items = []
                for item in arg:
                    if isinstance(item, basestring):
                        arg_items.append(IMPROPER_HTML_ENCODING.sub('', item))
                    else:
                        arg_items.append(item)
                new_args.extend(arg_items)
            elif isinstance(arg, basestring):
                proper_arg = IMPROPER_HTML_ENCODING.sub('', arg)
                new_args.append(proper_arg)
            else:
                new_args.append(arg)

        return tag_cls(*new_args, **kwargs)

    def data(self, key, value):
        return {'data-%s' % key: value}

    def entity(self, code):
        return Entity(code)

    # yui grid helpers:
    def grid(self, *args, **kwargs):
        (classes, kwargs) = extract_classes(kwargs)
        classes = classes + ("yui3-g",)
        return self.el('div', *args, class_=classes, **kwargs)

    # yui grid helpers:
    # html.unit(width="1-2", class_='myclass1', *[CONTENT])
    # html.unit(width="1-2", class_=('myclass1', 'myclass2',), *[CONTENT])
    # html.unit(witdh="1-2", CONTENT)
    # html.unit(CONTENT)
    def unit(self, *args, **kwargs):
        (classes, kwargs) = extract_classes(kwargs)

        width = kwargs.pop('width', "")
        mwidth = kwargs.pop('mwidth', None)
        if width is not "":
            width = "-%s" % width
        width_class = "yui3-u%s" % width

        mwidth_class = ""
        if mwidth:
            if mwidth is not "":
                mwidth = "-%s" % mwidth
            mwidth_class = "m-yui3-u%s" % mwidth

        classes = classes + (width_class, mwidth_class)

        return self.el('div', *args, class_=classes, **kwargs)

    # used in cases where you want either an <a> tag or a <span> tag
    # eg. in a list of people, some names should be linked (ie. friends) and some not (ie. strangers)
    # example: html.a_or_span(href=my_href, make_link=shoud_i_link_or_not, *[CONTENT])
    def a_or_span(self, *args, **kwargs):
        link = kwargs.pop('make_link')
        if link:
            tag = 'a'
        else:
            tag = 'span'
            kwargs.pop('href')
        return self.el(tag, *args, **kwargs)

    # wrapper will be a tag that each presenter is wrapped in (li, div, etc)
    # sep will be a tag that separates each presenter (hr, br, etc)
    # Note: this hasn't really been tested yet so if html.present doesn't work, this could very well be broken since it returns a list
    def present(self, presenters, wrapper=None, sep=None):
        if not is_seq_not_string(presenters):
            presenters = [presenters]

        # is there a better way to do this with itertools? maybe but it seems like not for the sep part
        output = []

        for p in presenters:
            if hasattr(p, 'render_html'):
                rendered = p.render_html()
            else:
                rendered = p
            if wrapper:
                rendered = wrapper(rendered)

            if is_seq_not_string(rendered) and not isinstance(rendered, HtmlElement):
                output.extend(rendered)
            else:
                output.append(rendered)

            if sep:
                output.append(sep)

        if sep:
            output = output[:-1]

        return output

    # Do not call these methods, the _ means they're private. Use class_=... and style=....
    def _classes(self, *classes):
        return {'class': _format_classes(_flatten_classes(classes))}

    # Turn a dictionary of style rules to the style attribute--no logic right now
    def _style(self, **styles):
        return {'style': "".join(["%s:%s;" % (k, v) for k, v in styles.iteritems()])}
