"""
Common helper methods to use in tubular scripts.
"""
import traceback

import click
from six import text_type


def _log(kind, message):
    """
    Convenience method to log text. Prepended "kind" text makes finding log entries easier.
    """
    click.echo('{}: {}'.format(kind, message))


def _fail(kind, code, message):
    """
    Convenience method to fail out of the command with a message and traceback.
    """
    _log(kind, message)

    # Try to get a traceback, if there is one. On Python 3.4 this raises an AttributeError
    # if there is no current exception, so we eat that here.
    try:
        _log(kind, traceback.format_exc())
    except AttributeError:
        pass

    exit(code)


def _fail_exception(kind, code, message, exc):
    """
    A version of fail that takes an exception to be utf-8 decoded
    """
    exc_msg = text_type(exc)

    # Slumber inconveniently discards the decoded .text attribute from the Response object, and
    # instead gives us the raw encoded .content attribute, so we need to decode it first. Using
    # hasattr here instead of try/except to keep our original exception intact.
    if hasattr(exc, 'content'):
        exc_msg += '\n' + exc.content.decode('utf-8')

    message += '\n' + exc_msg
    _fail(kind, code, message)
