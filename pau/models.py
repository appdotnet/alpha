from django.db import models
from django.contrib.auth.models import AbstractBaseUser, UserManager

from paucore.data.fields import DictField, CreateDateTimeField, LastModifiedDateTimeField
from paucore.data.pack2 import BoolPackField, Pack2, SinglePack2Container
from paucore.utils.python import memoized_property

from pau.bridge import APIUser


class UserPreferencesPack(Pack2):
    use_stream_markers = BoolPackField(key='usm', docstring='Use stream markers in pau?', default=False)
    show_unified_in_pau = BoolPackField(key='sup', docstring='Show the unified timeline for "my stream"?', default=False)
    disable_leading_mentions_filter = BoolPackField(key='dlmf', docstring='Disable twitter-style leading mentions filter',
                                                    default=False)


class PauUserManager(UserManager):
    def _create_user(self, username, *args, **kwargs):
        user = self.model(username=username)
        user.save()
        return user


class User(AbstractBaseUser):
    username = models.CharField(max_length=20, unique=True)

    # packs for prefs
    preferences = SinglePack2Container(pack_class=UserPreferencesPack, field_name='extra_info', pack_key='p')
    # jsonfield for full adn user object

    create_date = CreateDateTimeField()
    last_modified_date = LastModifiedDateTimeField()
    extra_info = DictField(blank=True, default=lambda: {})

    objects = PauUserManager()

    USERNAME_FIELD = 'username'

    def __unicode__(self):
        return "pk: %s, username: %s" % (self.pk, self.username)

    def get_full_name(self):
        return self.username

    def get_short_name(self):
        return self.get_full_name()

    @memoized_property()
    def adn_user(self):
        social_user = self.social_auth.get(provider="appdotnet")
        if not social_user:
            return

        adn_user = social_user.extra_data.get('user')
        if not adn_user:
            return

        return APIUser.from_response_data(adn_user)
