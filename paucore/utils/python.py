from collections import namedtuple
from functools import wraps, update_wrapper
from threading import Lock


#
# From: http://code.activestate.com/recipes/496741-object-proxying/
# __getattribute__ -> __getattr__ to make local stuff work.
#


class Proxy(object):

    __slots__ = ['_obj', '_overrides', '__weakref__']

    def __init__(self, obj):
        object.__setattr__(self, '_obj', obj)

    #
    # proxying (special cases)
    #

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, '_obj'), name)

    def __delattr__(self, name):
        delattr(object.__getattribute__(self, '_obj'), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, '_obj'), name, value)

    def __nonzero__(self):
        return bool(object.__getattribute__(self, '_obj'))

    def __str__(self):
        return str(object.__getattribute__(self, '_obj'))

    def __repr__(self):
        return repr(object.__getattribute__(self, '_obj'))

    #
    # factories
    #

    _special_names = [
        '__abs__', '__add__', '__and__', '__call__', '__cmp__', '__coerce__', '__contains__', '__delitem__', '__delslice__',
        '__div__', '__divmod__', '__eq__', '__float__', '__floordiv__', '__ge__', '__getitem__', '__getslice__', '__gt__',
        '__hash__', '__hex__', '__iadd__', '__iand__', '__idiv__', '__idivmod__', '__ifloordiv__', '__ilshift__', '__imod__',
        '__imul__', '__int__', '__invert__', '__ior__', '__ipow__', '__irshift__', '__isub__', '__iter__', '__itruediv__',
        '__ixor__', '__le__', '__len__', '__long__', '__lshift__', '__lt__', '__mod__', '__mul__', '__ne__', '__neg__',
        '__oct__', '__or__', '__pos__', '__pow__', '__radd__', '__rand__', '__rdiv__', '__rdivmod__', '__reduce__',
        '__reduce_ex__', '__repr__', '__reversed__', '__rfloorfiv__', '__rlshift__', '__rmod__', '__rmul__', '__ror__',
        '__rpow__', '__rrshift__', '__rshift__', '__rsub__', '__rtruediv__', '__rxor__', '__setitem__', '__setslice__',
        '__sub__', '__truediv__', '__xor__', 'next',
    ]

    @classmethod
    def _create_class_proxy(cls, theclass):
        '''creates a proxy for the given class'''

        def make_method(name):

            def method(self, *args, **kw):
                return getattr(object.__getattribute__(self, '_obj'), name)(*args, **kw)

            return method

        namespace = {}
        for name in cls._special_names:
            if hasattr(theclass, name):
                namespace[name] = make_method(name)

        return type('%s(%s)' % (cls.__name__, theclass.__name__), (cls,), namespace)

    def __new__(cls, obj, *args, **kwargs):
        '''
        creates an proxy instance referencing `obj`. (obj, *args, **kwargs) are
        passed to this class' __init__, so deriving classes can define an
        __init__ method of their own.
        note: _class_proxy_cache is unique per deriving class (each deriving
        class must hold its own cache)
        '''
        try:
            cache = cls.__dict__['_class_proxy_cache']
        except KeyError:
            cls._class_proxy_cache = cache = {}

        try:
            theclass = cache[obj.__class__]
        except KeyError:
            cache[obj.__class__] = theclass = cls._create_class_proxy(obj.__class__)

        ins = object.__new__(theclass)
        theclass.__init__(ins, obj, *args, **kwargs)

        return ins


def memoized_property(name=None):
    """Memoize an expensive computation as a property of an object"""
    def memoized_decorator(f):
        @property
        @wraps(f)
        def wrapper(self):
            cached_name = name
            if name is None:
                cached_name = "_cached_%s" % f.__name__

            if not hasattr(self, cached_name):
                val = f(self)
                setattr(self, cached_name, val)
            return getattr(self, cached_name)
        return wrapper
    return memoized_decorator


# todo refactor with above? doubtful
def memoized_method(name=None):
    """Memoize an expensive method computation based on args"""
    def memoized_decorator(f):
        @wraps(f)
        def wrapper(self, *args):
            cached_name = name
            if name is None:
                cached_name = "_cached_%s" % f.__name__

            if not hasattr(self, cached_name):
                setattr(self, cached_name, {})

            if args not in getattr(self, cached_name):
                val = f(self, *args)
                getattr(self, cached_name)[args] = val
            return getattr(self, cached_name)[args]
        return wrapper
    return memoized_decorator


def memoized_function(name=None):
    def memoized_decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            cached_name = name
            if name is None:
                cached_name = "_cached_%s" % f.__name__

            if not hasattr(f, cached_name):
                val = f(*args, **kwargs)
                setattr(f, cached_name, val)
            return getattr(f, cached_name)
        return wrapper
    return memoized_decorator


# stolen from http://code.activestate.com/recipes/576949-find-all-subclasses-of-a-given-class/
# modified to remove unused checks
# ----------------------
def itersubclasses(cls, _seen=None):
    if _seen is None:
        _seen = set()
    subs = cls.__subclasses__()
    for sub in subs:
        if sub not in _seen:
            _seen.add(sub)
            yield sub
            for sub in itersubclasses(sub, _seen):
                yield sub


def clamp_to_interval(val, bounds):
    min_bound, max_bound = bounds
    return min(max_bound, max(min_bound, val))


def cast_int(val, default=0, bounds=None):
    try:
        val = int(val)
        if bounds:
            return clamp_to_interval(val, bounds)
        return val
    except:
        return default


_CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])


# from http://code.activestate.com/recipes/578078-py26-and-py30-backport-of-python-33s-lru-cache/
# removed cases for maxsize=0, maxsize is None, so pyflakes doesn't complain
def lru_cache(maxsize=100, typed=False):
    """Least-recently-used cache decorator.

    If *typed* is True, arguments of different types will be cached separately.
    For example, f(3.0) and f(3) will be treated as distinct calls with
    distinct results.

    Arguments to the cached function must be hashable.

    View the cache statistics named tuple (hits, misses, maxsize, currsize) with
    f.cache_info().  Clear the cache and statistics with f.cache_clear().
    Access the underlying function with f.__wrapped__.

    See:  http://en.wikipedia.org/wiki/Cache_algorithms#Least_Recently_Used

    """

    # Users should only access the lru_cache through its public API:
    #       cache_info, cache_clear, and f.__wrapped__
    # The internals of the lru_cache are encapsulated for thread safety and
    # to allow the implementation to change (including a possible C version).

    def decorating_function(user_function):
        cache = dict()
        stats = [0, 0]                  # make statistics updateable non-locally
        HITS, MISSES = 0, 1             # names for the stats fields
        kwd_mark = (object(),)          # separate positional and keyword args
        cache_get = cache.get           # bound method to lookup key or return None
        _len = len                      # localize the global len() function
        lock = Lock()                   # because linkedlist updates aren't threadsafe
        root = []                       # root of the circular doubly linked list
        nonlocal_root = [root]                  # make updateable non-locally
        root[:] = [root, root, None, None]      # initialize by pointing to self
        PREV, NEXT, KEY, RESULT = 0, 1, 2, 3    # names for the link fields

        def make_key(args, kwds, typed, tuple=tuple, sorted=sorted, type=type):
            # helper function to build a cache key from positional and keyword args
            key = args
            if kwds:
                sorted_items = tuple(sorted(kwds.items()))
                key += kwd_mark + sorted_items
            if typed:
                key += tuple(type(v) for v in args)
                if kwds:
                    key += tuple(type(v) for k, v in sorted_items)
            return key

        def wrapper(*args, **kwds):
            # size limited caching that tracks accesses by recency
            key = make_key(args, kwds, typed) if kwds or typed else args
            with lock:
                link = cache_get(key)
                if link is not None:
                    # record recent use of the key by moving it to the front of the list
                    root, = nonlocal_root
                    link_prev, link_next, key, result = link
                    link_prev[NEXT] = link_next
                    link_next[PREV] = link_prev
                    last = root[PREV]
                    last[NEXT] = root[PREV] = link
                    link[PREV] = last
                    link[NEXT] = root
                    stats[HITS] += 1
                    return result
            result = user_function(*args, **kwds)
            with lock:
                root = nonlocal_root[0]
                if _len(cache) < maxsize:
                    # put result in a new link at the front of the list
                    last = root[PREV]
                    link = [last, root, key, result]
                    cache[key] = last[NEXT] = root[PREV] = link
                else:
                    # use root to store the new key and result
                    root[KEY] = key
                    root[RESULT] = result
                    cache[key] = root
                    # empty the oldest link and make it the new root
                    root = nonlocal_root[0] = root[NEXT]
                    del cache[root[KEY]]
                    root[KEY] = None
                    root[RESULT] = None
                stats[MISSES] += 1
            return result

        def cache_info():
            """Report cache statistics"""
            with lock:
                return _CacheInfo(stats[HITS], stats[MISSES], maxsize, len(cache))

        def cache_clear():
            """Clear the cache and cache statistics"""
            with lock:
                cache.clear()
                root = nonlocal_root[0]
                root[:] = [root, root, None, None]
                stats[:] = [0, 0]

        wrapper.__wrapped__ = user_function
        wrapper.cache_info = cache_info
        wrapper.cache_clear = cache_clear
        return update_wrapper(wrapper, user_function)

    return decorating_function


# From https://github.com/makinacorpus/easydict
class EasyDict(dict):
    def __init__(self, d=None, **kwargs):
        if d is None:
            d = {}
        if kwargs:
            d.update(**kwargs)
        for k, v in d.items():
            setattr(self, k, v)
        # Class attributes
        for k in self.__class__.__dict__.keys():
            if not (k.startswith('__') and k.endswith('__')):
                setattr(self, k, getattr(self, k))

    def __setattr__(self, name, value):
        if isinstance(value, (list, tuple)):
            value = [EasyDict(x) if isinstance(x, dict) else x for x in value]
        else:
            value = EasyDict(value) if isinstance(value, dict) else value
        super(EasyDict, self).__setattr__(name, value)
        self[name] = value
