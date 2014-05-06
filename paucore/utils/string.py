import re
from functools import partial

from django.contrib.auth.models import BaseUserManager


generate_random = partial(BaseUserManager.make_random_password.im_func, None)


def string_to_css_class(string):
    'Convert a string to a format useful for use as a css class.'
    if not string:
        return ''

    return string.lower().replace(' ', '_').replace('.', '_').replace('[', '_').replace(']', '_')


def possessive(str):
    if not str:
        return ''
    if str[-1] == 's':
        return "%s'" % str
    else:
        return "%s's" % str


def truncate(s, length=300, continuation="..."):
    if s:
        return (s[:length - len(continuation)] + continuation) if len(s) > length else s
    else:
        return ""


# Stolen from https://github.com/mitsuhiko/jinja2/blob/7d268bef0e8f3f12c0acb90f30d67726a3e3f261/jinja2/filters.py
# since there hasn't been a real release. When jinja2 goes to 2.7 we can delete this
# https://github.com/mitsuhiko/jinja2/pull/59
def do_filesizeformat(value, binary=False):
    """Format the value like a 'human-readable' file size (i.e. 13 kB,
    4.1 MB, 102 Bytes, etc).  Per default decimal prefixes are used (Mega,
    Giga, etc.), if the second parameter is set to `True` the binary
    prefixes are used (Mebi, Gibi).
    """
    bytes = float(value)
    base = binary and 1024 or 1000
    prefixes = [
        (binary and 'KiB' or 'kB'),
        (binary and 'MiB' or 'MB'),
        (binary and 'GiB' or 'GB'),
        (binary and 'TiB' or 'TB'),
        (binary and 'PiB' or 'PB'),
        (binary and 'EiB' or 'EB'),
        (binary and 'ZiB' or 'ZB'),
        (binary and 'YiB' or 'YB')
    ]
    if bytes == 1:
        return '1 Byte'
    elif bytes < base:
        return '%d Bytes' % bytes
    else:
        for i, prefix in enumerate(prefixes):
            unit = base ** (i + 2)
            if bytes < unit:
                return '%.1f %s' % ((base * bytes / unit), prefix)
        return '%.1f %s' % ((base * bytes / unit), prefix)


def camelcase_to_underscore(s):
    # stolen from http://stackoverflow.com/a/1176023
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', s)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
