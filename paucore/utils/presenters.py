from paucore.utils.htmlgen import HtmlGen


html = HtmlGen()


class AbstractPresenter(object):
    def generate_html(self):
        raise Exception("Not implemented")

    def generate_json(self, short=False):
        raise Exception("Not implemented")

    def render_html(self):
        if not getattr(self, 'visible', True):
            return ''
        if not hasattr(self, '_cached_html'):
            setattr(self, '_cached_html', self.generate_html())
        return self._cached_html

    def render_json(self, short=False):
        key = '_cached_short_json' if short else '_cached_json'
        if not hasattr(self, key):
            setattr(self, key, self.generate_json(short=short))
        return getattr(self, key)

    @classmethod
    def from_model(cls, model):
        """Factory method that creates the presenter from the model and pulls out/formats the appropriate data"""
        raise Exception("This presenter can't render class:%s" % model.__class__.__name__)


def html_list_to_english(L, with_period=False):
    'Convert a list into a string separated by commas and "and"'
    if len(L) == 0:
        return []
    elif len(L) == 1:
        res = L
    else:
        res = []

        for el in L[:-1]:
            res.append(el)
            res.append(", ")

        if res:
            # Why yes, I do give a fuck about an Oxford comma.
            res.pop()

        res.append(" and ")
        res.append(L[-1])

    if with_period:
        res.append('.')

    return res
