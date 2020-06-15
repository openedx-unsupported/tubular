#! /usr/bin/env python3

"""
Command-line script to click the "manual" gate in gocd.
"""

# pylint: disable=invalid-name


import os
import sys
from collections import namedtuple
from urllib.error import URLError
from urllib.request import urlopen

import backoff
import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

Service = namedtuple('service', ['name', 'host', 'port', 'path', 'enabled'])

SERVICES = [
    Service(
        'LMS',
        os.environ.get('LMS_HOST', 'localhost'),
        os.environ.get('LMS_PORT', 8000),
        os.environ.get('LMS_PATH', 'heartbeat'),
        os.environ.get('LMS_HEALTH_ENABLED', True),
    ),
    Service(
        'CMS',
        os.environ.get('CMS_HOST', 'localhost'),
        os.environ.get('CMS_PORT', 8001),
        os.environ.get('CMS_PATH', 'heartbeat'),
        os.environ.get('CMS_HEALTH_ENABLED', True),
    ),
    Service(
        'Ecommerce',
        os.environ.get('ECOMMERCE_HOST', 'localhost'),
        os.environ.get('ECOMMERCE_PORT', 8002),
        os.environ.get('ECOMMERCE_PATH', 'health/'),
        os.environ.get('ECOMMERCE_HEALTH_ENABLED', True),
    ),
    Service(
        'Forums',
        os.environ.get('FORUMS_HOST', 'localhost'),
        os.environ.get('FORUMS_PORT', 18080),
        os.environ.get('FORUMS_PATH', 'heartbeat??'),
        os.environ.get('FORUMS_HEALTH_ENABLED', False),
    ),
]


@click.command()
def check_health():
    """
    Check the health of all the services in the SERVICE array. Each individual service must be marked as enabled in
    order for the check to run.

    Returns:
        None

    """
    failed_services = []
    for service in SERVICES:
        if not service.enabled:
            pass
        url = 'http://{netloc}:{port}/{path}'.format(netloc=service.host, port=service.port, path=service.path)
        try:
            code = get_service_response_code(url)
            if code != 200:
                failed_services.append((
                    service, 'Service running but returns non 200 health response code. Code {}'.format(code)
                ))
        except URLError:
            failed_services.append((service, 'Connection Refused! Is the service running and the port correct?'))

    if failed_services:
        print("The following services have failed their health checks:")
        print(failed_services)
        sys.exit(1)

    sys.exit(0)


@backoff.on_predicate(backoff.constant, interval=5, max_tries=5)
@backoff.on_exception(backoff.constant, URLError, interval=5, max_tries=5)
def get_service_response_code(url):
    """
    Check to see if a service is available for a given URL.

    Args:
        url(str): the url for the service to be checked

    Returns:
        bool: True when the response code is 200

    Raises:
        URLError: if the service is unresponsive

    """
    return urlopen(url).code


if __name__ == "__main__":
    check_health()  # pylint: disable=no-value-for-parameter
