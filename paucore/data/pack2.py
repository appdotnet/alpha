import __builtin__
import collections
import pprint
from datetime import datetime

from paucore.data.fields import ReusedFieldKeyError, validate_pack_key_space
from paucore.utils.date import datetime_to_secs

from django.conf import settings


class PackField(object):
    "Stores a value in a Pack."

    get_normalizer = None
    set_normalizer = None
    validator = None

    def __init__(self, key, docstring=None, default=None, null_ok=False):
        self.key = key
        self.docstring = docstring
        self.default = default
        self.default_is_callable = isinstance(self.default, collections.Callable)
        self.null_ok = null_ok

    def __get__(self, obj, type=None):
        if obj is None:
            return self

        if self.default is None and self.key not in obj.values:
            return

        try:
            value = obj.values[self.key]
        except KeyError:
            if self.default_is_callable:
                value = self.default(obj)
            else:
                value = self.default

        if value is None:
            return

        if self.get_normalizer is not None:
            return self.get_normalizer(obj, value)
        else:
            return value

    def __set__(self, obj, value):
        if not obj:
            return

        if value is None:
            if self.null_ok:
                obj.values[self.key] = None
                return
            else:
                raise ValueError('Null value not permitted for field: %s' % self.key)

        if isinstance(self.validator, collections.Callable) and not self.validator(obj, value):
            raise ValueError('Validation failed (callable) for field: %s value: %s' % (self.key, value))

        if isinstance(self.set_normalizer, collections.Callable):
            value = self.set_normalizer(obj, value)

        obj.values[self.key] = value

    def __delete__(self, obj):
        del obj.values[self.key]


class IntegerPackField(PackField):
    "Stores an integer in a Pack."

    def get_normalizer(self, obj, value):
        return __builtin__.int(value)

    def set_normalizer(self, obj, value):
        return __builtin__.int(value)

    def validator(self, obj, value):
        try:
            __builtin__.int(value)
            return True
        except:
            return False


class FloatPackField(PackField):
    "Stores a float in a Pack."

    def get_normalizer(self, obj, value):
        return __builtin__.float(value)

    def set_normalizer(self, obj, value):
        return __builtin__.float(value)

    def validator(self, obj, value):
        try:
            __builtin__.float(value)
            return True
        except:
            return False


class BoolPackField(PackField):
    "Stores a boolean in a Pack as an integer (0 or 1)."

    def get_normalizer(self, obj, value):
        return bool(value)

    def set_normalizer(self, obj, value):
        if bool(value):
            return 1
        else:
            return 0

    def validator(self, obj, value):
        try:
            bool(value)
            return True
        except:
            return False


class ChoicesPackField(PackField):
    "Stores a Choices object in a Pack. Validates class."

    def __init__(self, choices, **kwargs):
        super(ChoicesPackField, self).__init__(**kwargs)
        self.choices = choices

    def get_normalizer(self, obj, value):
        return __builtin__.int(value)

    def set_normalizer(self, obj, value):
        return __builtin__.int(value)

    def validator(self, obj, value):
        try:
            int_val = __builtin__.int(value)
            return int_val in self.choices
        except:
            return False


class DateTimePackField(PackField):
    "Stores a datetime object in a Pack as a UTC epoch timestamp."

    def get_normalizer(self, obj, value):
        return datetime.utcfromtimestamp(value)

    def set_normalizer(self, obj, value):
        return datetime_to_secs(value)

    def validator(self, obj, value):
        return isinstance(value, datetime)


class ListPackField(PackField):
    """Store a list in a Pack with an optional item normalizer"""
    item_normalizer = None

    def __init__(self, **kwargs):
        kwargs.setdefault('default', lambda _: [])
        super(ListPackField, self).__init__(**kwargs)

    def get_normalizer(self, obj, value):
        return map(self.item_normalizer, value)

    def set_normalizer(self, obj, value):
        return map(self.item_normalizer, value)

    def validator(self, obj, value):
        try:
            map(self.item_normalizer, value)
            return True
        except:
            return False


class ListOfIDsPackField(ListPackField):
    "Stores a list of IDs in a Pack."
    normalizer = __builtin__.int


class SetPackField(PackField):
    """ Stores a set type in a Pack as a list. """
    item_normalizer = None
    item_validator = None

    def __init__(self, **kwargs):
        kwargs.setdefault('default', lambda _: set())
        super(SetPackField, self).__init__(**kwargs)

    def get_normalizer(self, obj, value):
        return set(map(self.item_normalizer, value))

    def set_normalizer(self, obj, value):
        return list(set(map(self.item_normalizer, value)))

    def validator(self, obj, value):
        try:
            set(value)
            return all(map(self.item_validator, value)) if self.item_validator else True
        except:
            return False


class SetOfIDsPackField(SetPackField):
    "Stores a set of IDs in a Pack."
    item_normalizer = __builtin__.int
    item_validator = __builtin__.int


class SetOfChoicesPackField(SetPackField):
    """ Stores a set of Choices in a Pack """

    item_normalizer = __builtin__.int

    def __init__(self, **kwargs):
        choices = kwargs.pop('choices')
        super(SetOfChoicesPackField, self).__init__(**kwargs)
        self.choices = choices
        self.item_validator = lambda val: __builtin__.int(val) in self.choices


class Pack2(object):
    "Base class for Pack2 objects."

    def __init__(self, parent, values, key=None):
        self.parent = parent
        self.values = values
        self.key = key

    @classmethod
    def dummy(cls):
        return cls(None, {})

    @property
    def pack_info(self):
        for k in dir(self):
            try:
                f = getattr(self.__class__, k)
                if isinstance(f, PackField) or (isinstance(f, AbstractPack2Container) and k != 'parent'):
                    yield (k, f)
            except:
                pass

    def copy_to(self, dest):
        for k, f in self.pack_info:
            if isinstance(f, PackField):
                setattr(dest, k, getattr(self, k))
            elif isinstance(f, SinglePack2Container):
                pack = getattr(self, k)
                pack.copy_to(getattr(dest, k))
            elif isinstance(f, DictPack2Container):
                pack_dict = getattr(self, k)
                dest_dict = getattr(dest, k)
                for key, pack in pack_dict.iteritems():
                    pack.copy_to(dest_dict[key])
            else:
                raise NotImplementedError('unknown Pack2Container type: %s' % f)

    @classmethod
    def validate_key_space(cls):
        seen_keys = set([])
        for k in dir(cls):
            try:
                f = getattr(cls, k)
            except:
                continue
            field_key = None
            if isinstance(f, PackField):
                field_key = f.key
            elif isinstance(f, AbstractPack2Container) and k != 'parent':
                # todo - recursive call here? we don't have an instance yet so we may need some kind of namespace
                field_key = f.pack_key
            if field_key:
                if field_key in seen_keys:
                    raise ReusedFieldKeyError('Reused pack field key=%s on pack=%s' % (field_key, cls.__name__))
                seen_keys.add(field_key)

    def __repr__(self):
        pretty_values = {k: getattr(self, k) for (k, _) in self.pack_info}

        return '<Pack2(%s.%s): %s>' % (self.__class__.__module__, self.__class__.__name__, pprint.pformat(pretty_values))


class AbstractPack2Container(object):
    "Container for pack objects."

    def __init__(self, pack_class, pack_key, field_name='extra_info'):
        self.pack_class = pack_class
        self.pack_key = pack_key
        self.field_name = field_name

    def get_pack_cache(self, obj):
        key = '_pack_cache__%s' % (self.field_name)
        try:
            return getattr(obj, key)
        except AttributeError:
            val = {}
            setattr(obj, key, val)
            return val

    def __get__(self, obj, type=None):
        if obj is None:
            return self

        pack_cache = self.get_pack_cache(obj)
        if self.pack_key not in pack_cache:
            field = getattr(obj, self.field_name)
            if self.pack_key not in field:
                field[self.pack_key] = {}

            pack_cache[self.pack_key] = self.create(obj, field[self.pack_key])

        return pack_cache[self.pack_key]

    def validate_key_space(self, sender):
        self.pack_class.validate_key_space()
        validate_pack_key_space(sender, self.field_name, self.pack_key)

    def contribute_to_class(self, sender, inst_name):
        setattr(sender, inst_name, self)
        if settings.ENVIRONMENT != 'prod':
            self.validate_key_space(sender)


class SinglePack2Container(AbstractPack2Container):
    "Store a single Pack object on a model."

    def create(self, parent, values):
        return self.pack_class(parent, values)


class _Pack2Dict(collections.defaultdict):
    make_key = unicode

    def __init__(self, pack_class, parent, values):
        super(_Pack2Dict, self).__init__()
        self.pack_class = pack_class
        self.parent = parent
        self.values = values

        for k, v in values.iteritems():
            k = self.make_key(k)
            super(_Pack2Dict, self).__setitem__(k, self.pack_class(parent=self.parent, key=k, values=v))

    def __missing__(self, key):
        key = self.make_key(key)
        value = self.pack_class(parent=self.parent, key=key, values={})
        super(_Pack2Dict, self).__setitem__(key, value)
        self.values[key] = value.values

        return value

    def __setitem__(self, i, y):
        raise ValueError('DictPack2Container does not support adding values')

    def __delitem__(self, y):
        key = self.make_key(y)
        super(_Pack2Dict, self).__delitem__(key)
        del self.values[unicode(key)]

    def clear(self):
        super(_Pack2Dict, self).clear()
        self.values.clear()


class DictPack2Container(AbstractPack2Container):
    "Store a dictionary of Pack objects on a model."

    def create(self, parent, values):
        return _Pack2Dict(self.pack_class, parent, values)


class _Pack2AutoIncrementDict(_Pack2Dict):
    """This can be thought of as just a list even though it's represented as a dict"""

    make_key = int

    def __init__(self, pack_class, parent, values):
        next_val = int(values.pop('n', 0))
        super(_Pack2AutoIncrementDict, self).__init__(pack_class, parent, values)
        self.values['n'] = next_val

    def new_item(self):
        """Always call this within an edit decorator to lock"""
        idx = self.values['n']
        new_item = self[idx]
        self.values['n'] += 1
        return (idx, new_item)


class AutoIncrementDictPack2Container(AbstractPack2Container):
    "Store an auto incrementing keyed dictionary of Pack objects on a model."

    def create(self, parent, values):
        return _Pack2AutoIncrementDict(self.pack_class, parent, values)
