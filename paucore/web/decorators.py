from functools import wraps

from django.utils.decorators import available_attrs


def ssl_only(view_func):
    """
    Modifies a view function so that it is always viewed
    over SSL.
    """
    def wrapped_view(*args, **kwargs):
        return view_func(*args, **kwargs)
    wrapped_view.ssl_only = True
    return wraps(view_func, assigned=available_attrs(view_func))(wrapped_view)


def ignore_ssl(view_func):
    """
    Modifies a view function so that it is exempt from SSL handling.
    """
    def wrapped_view(*args, **kwargs):
        return view_func(*args, **kwargs)
    wrapped_view.ignore_ssl = True
    return wraps(view_func, assigned=available_attrs(view_func))(wrapped_view)
