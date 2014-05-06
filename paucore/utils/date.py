import calendar
import itertools
import pytz

from datetime import datetime

from django.utils.translation import ugettext_lazy as _

MXML_ISO_STRF_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
ALL_TIMEZONE_CHOICES = tuple(itertools.izip(*itertools.tee(pytz.all_timezones, 2)))
FANCY_COMMON_TIMEZONES = tuple(itertools.izip(*itertools.tee(pytz.common_timezones, 2)))

# just the values, not a "choices"
COMMON_TIMEZONES = pytz.common_timezones

JUST_NOW = _("now")
SECONDS_AGO = _("%(seconds)ds")
MINUTES_AGO = _("%(minutes)dm")
HOURS_AGO = _("%(hours)dh")
DAYS_AGO = _("%(count)dd")
WEEKS_AGO = _("%(count)dw")

OLDER_CHUNKS = (
    (7.0, 1.0, DAYS_AGO),
    (30.0, 7.0, WEEKS_AGO),
)


def append_ago(base, ago_suffix=False):
    if ago_suffix:
        return base + u' ago'
    else:
        return base


def naturaldate(date, just_now=JUST_NOW, ago_suffix=False, start_date=None, older_chunks=OLDER_CHUNKS):
    """Convert datetime into a human natural date string."""

    if not date:
        return unicode('')

    if not start_date:  # MATTHEW.
        start_date = datetime.now()

    today = datetime(start_date.year, start_date.month, start_date.day)
    delta = start_date - date
    delta_midnight = today - date

    days = delta.days
    hours = round(delta.seconds / 3600, 0)
    minutes = delta.seconds / 60

    if days < 0:
        return unicode(just_now)

    if days == 0:
        if hours == 0:
            if minutes > 0:
                return append_ago(unicode(MINUTES_AGO % {"minutes": minutes}), ago_suffix=ago_suffix)
            else:
                return unicode(just_now)
        else:
            return append_ago(unicode(HOURS_AGO % {"hours": hours}), ago_suffix=ago_suffix)

    for limiter, chunk, text in older_chunks:
        if days <= limiter:
            count = round((delta_midnight.days + 1) / chunk, 0)
            return append_ago(unicode(text % ({"count": count})), ago_suffix=ago_suffix)

    if days <= 365:
        return date.strftime('%d %b')

    return date.strftime('%d %b %y')


def datetime_to_secs(dt):
    # http://stackoverflow.com/questions/2956886/python-calendar-timegm-vs-time-mktime
    return int(calendar.timegm(dt.utctimetuple()))
