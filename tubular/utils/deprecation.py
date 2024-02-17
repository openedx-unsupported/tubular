import warnings

import click


def deprecated_script(func):
    def wrapper(*args, **kwargs):
        warning = f"WARNING: Script {func.__module__} has been marked deprecated and " \
                  f"migrated to within 'edx-platform' repository."
        warnings.warn(warning, DeprecationWarning, stacklevel=3)
        click.secho(warning, fg="yellow", bold=True)
        func(*args, **kwargs)

    return wrapper
