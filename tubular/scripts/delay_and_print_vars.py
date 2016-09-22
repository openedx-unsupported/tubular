"""
Script to simply delay and then print the specified environment variables.
"""
from __future__ import unicode_literals

import os
import sys
import time
import random
import click


@click.command()
@click.option(
    '--success_prob', '-p',
    default=100,
    help="Probability percent of successful script completion (0-100).",
    type=int,
)
@click.argument('env_vars', nargs=-1)
def cli(success_prob, env_vars):
    """
    Sleep for a random amount of time.
    Output the values of the specified environment variables.
    Succeed mainly, randomly fail some percentage of the time.
    """
    delay_seconds = random.uniform(0.5, 10)
    time.sleep(delay_seconds)

    for var in env_vars:
        print "{:20} => {:10}".format(var, os.environ[var])

    # Fail some percentage of the time.
    status_success = True
    if random.randint(1, 100) > success_prob:
        status_success = False

    # An exit code of 0 means success and non-zero means failure.
    print "Script will now simulate a {}...".format('success' if status_success else 'failure')
    sys.exit(not status_success)


if __name__ == '__main__':
    cli()  # pylint: disable=no-value-for-parameter
