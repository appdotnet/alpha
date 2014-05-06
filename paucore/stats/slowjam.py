import threading
import time
from contextlib import contextmanager
from collections import defaultdict

from django.conf import settings

from paucore.utils.python import Proxy

# is this enough control if things start blowing up and we want to turn off slowjam without rolling? do we need it to be?
_slowjam_profiling = getattr(settings, 'SLOWJAM_ENABLED', True)
_default_lambda = lambda: 0


def enable_profiling():
    global _slowjam_profiling
    _slowjam_profiling = True


def disable_profiling():
    global _slowjam_profiling
    _slowjam_profiling = False


def can_profile():
    return _slowjam_profiling


class CounterDict(defaultdict):
    """We don't want a collections.Counter here because we often store non-counter things in the extras dict."""

    def __init__(self, *args, **kwargs):
        super(CounterDict, self).__init__(_default_lambda, *args, **kwargs)

    def incr(self, key, delta=1):
        try:
            self[key] = int(self[key]) + delta
        except ValueError:
            self[key] = delta


class DummyDict(object):

    def incr(self, key, delta=1):
        pass

    def __getitem__(self, key):
        pass

    def __setitem__(self, key, value):
        pass


dummy_dict = DummyDict()


class ProfileContext(object):

    def __init__(self, event, fmt=None, extras=None, tag=None, is_marker=False, start_time=None, stop_time=None, should_show=True):
        self.event = event
        self.should_show = should_show

        self.start_time = start_time or time.time()
        if stop_time:
            self.stop_time = stop_time
        else:
            self.stop_time = self.start_time if is_marker else None

        self.is_marker = is_marker
        self.fmt = fmt
        self.tag = tag
        self.extras = extras if is_marker else CounterDict(extras or {})
        self.inner_events = []

    def stop(self):
        if not self.is_marker:
            self.stop_time = time.time()

    @property
    def execution_time(self):
        if self.stop_time:
            return (self.stop_time - self.start_time) * 1000

    @property
    def pretty_execution_time(self):
        et = self.execution_time
        if et:
            return u'(+%5d ms)' % et

        return '(  running)'

    def render_event(self, epoch, indent=0):
        epoch = epoch or self.start_time
        indented = ' |' * indent
        #     '(+50000 ms)'
        pad = '           '

        if not self.stop_time:
            self.stop_time = self.start_time
            pad = '   BONED   '

        offset = '%8d ms' % ((self.start_time - epoch) * 1000)
        formatted_extras = ''

        if self.extras:
            if self.fmt:
                try:
                    formatted_extras = ''.join((' [', self.fmt % self.extras, ']'))
                except:
                    formatted_extras = ' (error formatting extras)'
            else:
                keys = sorted(self.extras.keys())
                formatted_extras = ''.join((
                    u' [',
                    u' '.join((u''.join((unicode(k), '=', unicode(self.extras[k]))) for k in keys)),
                    u']',
                ))
        elif self.fmt:
            formatted_extras = ''.join((' [', self.fmt, ']'))

        fmt = '%s %s%s %s %s%s'

        if self.is_marker:
            rv = [fmt % (offset, pad, indented, '@', self.event, formatted_extras)]
        elif not self.inner_events:
            rv = [fmt % (offset, self.pretty_execution_time, indented, '=', self.event, formatted_extras)]
        else:
            rv = [fmt % (offset, pad, indented, '+', self.event, formatted_extras)]

        if self.inner_events:
            for child in self.inner_events:
                if child.should_show:
                    rv.extend(child.render_event(epoch, indent + 1))

            rv.append('%s %s%s +' % (pad, self.pretty_execution_time, indented))

        return rv

    def __str__(self):
        header = ['       time   exec time event', '----------- ----------- ------------------------------']
        return '\n'.join(header + self.render_event(None))

    def to_dict(self):
        return {
            'event': self.event,
            'start_time': self.start_time,
            'stop_time': self.stop_time,
            'is_marker': self.is_marker,
            'fmt': self.fmt,
            'tag': self.tag,
            'extras': self.extras,
            'inner_events': [event.to_dict() for event in self.inner_events],
        }

    @classmethod
    def from_dict(klass, d):
        obj = klass(event=d['event'], start_time=d['start_time'], stop_time=d['stop_time'], is_marker=d['is_marker'], fmt=d['fmt'],
                    tag=d['tag'], extras=d['extras'])
        obj.inner_events = [klass.from_dict(event_dict) for event_dict in d['inner_events']]

        return obj


class ProfileGlobalContext(threading.local):
    _started = False
    enabled_tags = set()

    def start(self, event, fmt=None, extras=None, tag=None):
        if not _slowjam_profiling:
            return

        self._started = True
        self._stack = [ProfileContext(event, fmt, extras, tag)]

    def stop(self):
        if not self.profiling:
            return

        stack = self._stack
        self._started = False
        self._stack = []

        if stack:
            profile = stack[0]
            profile.stop()

            return profile

    def push(self, event, fmt=None, extras=None, tag=None):
        if not self.profiling:
            return

        should_show = not tag or (tag in slowjam_context.enabled_tags) or ('all' in slowjam_context.enabled_tags)

        profile = ProfileContext(event, fmt, extras, tag, should_show=should_show)
        self._stack[-1].inner_events.append(profile)
        self._stack.append(profile)

        return profile

    def pop(self):
        if not self.profiling:
            return

        profile = self._stack.pop()
        profile.stop()

    @contextmanager
    def event(self, event, fmt=None, extras=None, tag=None):
        child = self.push(event, fmt, extras, tag)

        if child:
            yield child.extras
            self.pop()
        else:
            yield dummy_dict

    def mark(self, event, fmt=None, extras=None, tag=None):
        if not self.profiling:
            return

        self._stack[-1].inner_events.append(ProfileContext(event, fmt, extras, tag, is_marker=True))

    @property
    def profiling(self):
        return _slowjam_profiling and self._started


_thread_slowjam_context = threading.local()


def get_slowjam_context():
    if _slowjam_profiling:
        if not getattr(_thread_slowjam_context, 'slowjam_context', None):
            _thread_slowjam_context.slowjam_context = ProfileGlobalContext()
        return Proxy(_thread_slowjam_context.slowjam_context)


slowjam_context = get_slowjam_context()
