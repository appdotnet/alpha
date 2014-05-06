import logging
import collections
from datetime import datetime
# Must be system JSON -- DjangoJSONEncoder relies on this
import json

from django.db import models
from django.core.serializers.json import DjangoJSONEncoder


logger = logging.getLogger(__name__)


class ReusedFieldKeyError(Exception):
    pass


class ReusedPackKeyError(Exception):
    pass


def validate_pack_key_space(parent, field_name, pack_key):
    reserved_pack_keys = getattr(parent, '__reserved_pack_keys__', collections.defaultdict(set))
    if pack_key in reserved_pack_keys[field_name]:
        raise ReusedPackKeyError('pack_key=%s reused on field=%s on model=%s' % (pack_key, field_name, parent))
    reserved_pack_keys[field_name].add(pack_key)
    setattr(parent, '__reserved_pack_keys__', reserved_pack_keys)


class DictField(models.Field):
    """DictField is a textfield that contains JSON-serialized dictionaries."""

    # Used so to_python() is called
    __metaclass__ = models.SubfieldBase

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('editable', False)
        super(DictField, self).__init__(*args, **kwargs)

    def get_default(self):
        if self.has_default():
            if callable(self.default):
                return self.default()
            return self.default
        # If the field doesn't have a default, then we punt to models.Field.
        return super(DictField, self).get_default()

    def to_python(self, value):
        """Convert our string value to JSON after we load it from the DB"""
        if not value:
            return {}

        if isinstance(value, basestring):
            value = json.loads(value)

        assert isinstance(value, dict)

        return value

    def get_db_prep_value(self, value, connection=None, prepared=False):
        """Convert our JSON object to a string before we save"""
        assert isinstance(value, dict)

        return json.dumps(value, cls=DjangoJSONEncoder, separators=(',', ':'))

    def get_internal_type(self):
        return 'TextField'

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return self.get_db_prep_value(value)

    def get_db_prep_lookup(self, lookup_type, value, connection=None, prepared=False):
        raise TypeError('Lookups not supported for DictField.')


class Choices(object):
    """
    swiped from: http://www.djangosnippets.org/snippets/1647/
    & slightly modified by bryan

    A small helper class for more readable enumerations,
    and compatible with Django's choice convention.
    You may just pass the instance of this class as the choices
    argument of model/form fields.

    Example:
        MY_ENUM = Choices(
            (100, 'MY_NAME', 'My verbose name'),
            (200, 'MY_AGE', 'My verbose age'),
        )
        assert MY_ENUM.MY_AGE == 100
        assert MY_ENUM[1] == (200, 'My verbose age')
    """

    def __init__(self, *args):
        self.enum_list = [(item[0], item[2]) for item in args]
        self.key_list = [item[0] for item in args]
        self.enum_dict = {}
        self.to_enum_dict = {}
        self.str_dict = {}
        self._raw_choices = args
        seen_numerals = set()
        seen_names = set()
        for item in args:
            if item[0] in seen_numerals:
                raise ReusedFieldKeyError('Reused Choice numeral=%s for %s' % (item[0], item))
            seen_numerals.add(item[0])

            if item[1] in seen_names:
                raise ReusedFieldKeyError('Reused Choice name=%s for %s' % (item[1], item))
            seen_names.add(item[1])

            self.enum_dict[item[1]] = item[0]
            self.to_enum_dict[item[0]] = item[1]
            self.str_dict[item[0]] = item[2]

    def __contains__(self, v):
        return (v in self.key_list)

    def __len__(self):
        return len(self.enum_list)

    def __getitem__(self, v):
        if isinstance(v, basestring):
            return self.enum_dict[v]
        elif isinstance(v, int):
            return self.enum_list[v]

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, v):
        self.__dict__ = v

    def __getattr__(self, name):
        return self.enum_dict[name]

    def __iter__(self):
        return self.enum_list.__iter__()

    def const_by_key(self, key):
        return self.to_enum_dict[key]

    def display_string(self, key):
        return self.str_dict[key]

    def slug(self, key):
        return self.to_enum_dict[key].lower()

    def for_slug(self, slug):
        return self[slug.upper()]


class CreateDateTimeField(models.DateTimeField):

    def __init__(self, *args, **kwargs):
        kwargs['default'] = datetime.utcnow
        kwargs['blank'] = True
        models.DateTimeField.__init__(self, *args, **kwargs)


class LastModifiedDateTimeField(models.DateTimeField):

    def __init__(self, *args, **kwargs):
        kwargs['blank'] = True
        models.DateTimeField.__init__(self, *args, **kwargs)

    def pre_save(self, model_instance, add):
        value = datetime.utcnow()
        setattr(model_instance, self.attname, value)
        return value
