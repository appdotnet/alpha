import itertools
import logging
import math
import operator
import time

from contextlib import contextmanager

import simplejson as json
from django.core.cache import cache

from paucore.stats.statsd_client import graphite_timer

logger = logging.getLogger(__name__)


def chunks(l, n=1000):
    """ Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i + n]


def qs_chunks(qs):
    return chunks(qs.values_list('pk', flat=True))


def qs_iter(qs, checkpoint=False, bulk_load_everything=False):
    iter_count = 0
    for pk_chunk in qs_chunks(qs):
        if checkpoint:
            logger.info('(checkpoint: iter=%d pk_chunk=%d..%d)', iter_count, pk_chunk[0], pk_chunk[-1])

        objs = qs.model.objects.by_pk(pk_chunk)

        if bulk_load_everything:
            qs.model.objects.bulk_load_everything(objs)

        for obj in objs:
            yield obj

        iter_count += 1


def uniquify_slug(s, klass, slug_field='slug', filter_dict=None, exclude_dict=None):
    slug = s

    def get_query():
        query = klass.objects.filter(**{slug_field: slug})
        if filter_dict:
            query = query.filter(**filter_dict)
        if exclude_dict:
            query = query.exclude(**exclude_dict)

        return query.exists()

    counter = 1
    while get_query():
        slug = "%s-%s" % (s, counter)
        counter += 1

    return slug


def extract_id(model):
    "Allows a method to take either a pk or a model"
    try:
        return model.pk
    except AttributeError:
        return model


def is_iterable(obj):
    try:
        iter(obj)
        return True
    except:
        return False


def is_seq_not_string(obj):
    if isinstance(obj, basestring):
        return False

    return is_iterable(obj)


def dict_map(func, d):
    """takes dictionary d whose values are lists and maps func over all the values lists"""

    return {k: map(func, list_) for k, list_ in d.iteritems()}


def dict_drop_empty(keys, vals):
    """Take keys and values and turn them into a dictionary, dropping keys if there is no value"""

    return {k: v for (k, v) in itertools.izip(keys, vals) if v}


# '' -> omitted key
# {} -> omitted key
# null -> omitted key
# Null -> omitted key
# colander.null -> omitted key (colander.null -> None is handled in json_serialize_obj)
# [] -> []
# false -> false
# 0 -> 0
def _should_keep(v):
    # if it's 'True-ish' or it's an empty list, or it's False, or it's 0
    return v or v == [] or v is False or v == 0


def dict_drop_implicit_falsey(data, skip_keys=None):
    try:
        ret_d = {}
        for k, v in data.iteritems():
            if skip_keys and k in skip_keys:
                ret_d[k] = v
            else:
                new_v = dict_drop_implicit_falsey(v, skip_keys=skip_keys)
                if _should_keep(new_v):
                    ret_d[k] = new_v
        return ret_d
    except AttributeError:
        # if data is not a dict, move on
        pass

    if not isinstance(data, basestring):
        try:
            return [dict_drop_implicit_falsey(d, skip_keys=skip_keys) for d in data]
        except TypeError:
            # if it's not a list/iterable
            pass

    return data


def identity(s):
    return s


# Be warned, sometimes we got None out of iterable even though None wasn't in iterable according to Sentry--that's because Sentry's
# pretty printer ignores None in lists, look at the raw json data in sentry for the real data
def partition(pred, iterable):
    'Use a predicate to partition entries into false entries and true entries'
    # python itertools recipe
    t1, t2 = itertools.tee(iterable)
    return itertools.ifilterfalse(pred, t1), itertools.ifilter(pred, t2)


# Taken from the itertools recipes: http://docs.python.org/dev/library/itertools.html#itertools-recipes
def flatten(list_of_lists):
    "Flatten one level of nesting"
    return itertools.chain.from_iterable(list_of_lists)


def grouper(n, iterable, fillvalue=None):
    "grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return itertools.izip_longest(fillvalue=fillvalue, *args)


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.izip(a, b)


def id_query(entities, query_key='pk', id_normalization_callable=None):
    if is_seq_not_string(entities):
        if id_normalization_callable:
            ids = [id_normalization_callable(extract_id(x)) for x in entities]
        else:
            ids = [extract_id(x) for x in entities]
        if len(ids) == 1:
            return {query_key: ids[0]}
        else:
            return {query_key + '__in': ids}
    else:
        if id_normalization_callable:
            return {query_key: id_normalization_callable(extract_id(entities))}
        else:
            return {query_key: extract_id(entities)}


def make_id_list(entities, query_key='pk', id_normalization_callable=identity):
    if is_seq_not_string(entities):
        if id_normalization_callable:
            return [id_normalization_callable(extract_id(x)) for x in entities]
        else:
            return [extract_id(x) for x in entities]
    else:
        if id_normalization_callable:
            return [id_normalization_callable(extract_id(entities)) for x in entities]
        else:
            return [extract_id(entities) for x in entities]


def bulk_load_related(objs, field_name):
    with graphite_timer('c4g.bulk_load_related', extras={'field': field_name}) as timer:
        if not objs:
            timer['empty'] = True
            return []

        if not is_seq_not_string(objs):
            # if we were passed a single object, make it a list
            objs = [objs]

        timer.incr('objs', len(objs))

        sample_obj = objs[0]
        field = sample_obj._meta.get_field(field_name)
        timer['model'] = '%s.%s' % (sample_obj._meta.app_label, sample_obj._meta.module_name)
        cache_name = field.get_cache_name()

        # Additionally: possibly update this to coalesce objects
        pending_objs = itertools.ifilter(lambda obj: not hasattr(obj, cache_name), objs)
        unique_fks = set(itertools.ifilter(None, (itertools.imap(operator.attrgetter(field.attname), pending_objs))))

        related_objs = field.rel.to._c4g_manager.by_pks_as_dict(unique_fks)
        for obj in objs:
            related_obj_id = getattr(obj, field.attname)
            if hasattr(obj, cache_name):
                # In this case, we want to reduce all of the related objs
                # to a single instance
                if related_obj_id not in related_objs:
                    related_objs[related_obj_id] = getattr(obj, cache_name)
                else:
                    setattr(obj, cache_name, related_objs[related_obj_id])

                continue

            related_obj = related_objs.get(related_obj_id)
            if field.null or related_obj:
                setattr(obj, cache_name, related_obj)
            if field.unique and related_obj:
                setattr(related_obj, field.related.get_cache_name(), obj)

        return related_objs.values()


def dict_values_to_set(d):
    s = set()
    for v in d.values():
        if is_seq_not_string(v):
            s.update(v)
        else:
            s.add(v)
    return s


def get_page_slice(list_, page_number, page_size):
    if page_size == -1:
        return list_

    start_idx = page_number * page_size
    if start_idx > len(list_):
        return []

    return list_[start_idx:start_idx + page_size]


def uniquify_list(seq, idfun=None):
    # order preserving
    if idfun is None:

        def idfun(x):
            return x

    seen = {}
    result = []
    for item in seq:
        marker = idfun(item)
        # in old Python versions:
        # if seen.has_key(marker)
        # but in new ones:
        if marker in seen:
            continue
        seen[marker] = 1
        result.append(item)
    return result


class CacheLockFailed(Exception):
    pass


@contextmanager
def cache_lock(lock_key, lock_timeout=15, poll_interval=0.5, retry_count=None):
    cache_key = '__d_lock_%s' % lock_key
    acquired = False

    try:
        _acquire_lock(cache_key, lock_key, lock_timeout, poll_interval, retry_count)
        acquired = True
        yield
    finally:
        if acquired:
            _release_lock(cache_key)


def _acquire_lock(cache_key, lock_key, lock_timeout, poll_interval, retry_count):
    if retry_count is None:
        retry_count = int(math.ceil(lock_timeout / poll_interval))

    for i in xrange(0, retry_count):
        stored = cache.add(cache_key, 1, lock_timeout)
        if stored:
            return
        time.sleep(poll_interval)

    raise CacheLockFailed('Attempted to acquire lock for key %s, but failed' % lock_key)


def _release_lock(cache_key):
    cache.delete(cache_key)


def first(c, iterable):
    return next(itertools.ifilter(c, iterable), None)


def take(iterable, n=1000):
    """ stolen right off of http://docs.python.org/2/library/itertools.html#recipes """
    return list(itertools.islice(iterable, n))


def is_string_subset(subset, superset):
    if is_seq_not_string(subset):
        return set(map(lambda t: t.lower(), subset)).issubset(superset)
    else:
        return subset.lower() in superset


def lazy_chunks(iterable, n=1000):
    while True:
        chunk = take(iterable, n)
        if chunk:
            yield chunk
        else:
            break


def json_iter_for_line_iter(line_iter):
    return itertools.imap(json.loads, itertools.ifilter(None, line_iter))


def percentile(N, percent, key=lambda x: x):
    """
    Find the percentile of a list of values.

    @parameter N - is a list of values. Note N MUST BE already sorted.
    @parameter percent - a float value from 0.0 to 1.0.
    @parameter key - optional key function to compute value from each element of N.

    @return - the percentile of the values
    http://stackoverflow.com/a/2753343
    """
    if not N:
        return None
    k = (len(N) - 1) * percent
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return key(N[int(k)])
    d0 = key(N[int(f)]) * (c - k)
    d1 = key(N[int(c)]) * (k - f)
    return d0 + d1


def intersperse(delimiter, seq):
    return itertools.islice(itertools.chain.from_iterable(itertools.izip(itertools.repeat(delimiter), seq)), 1, None)
