#! /usr/bin/env python3

"""
Command-line script to get open prs with label 'Ready to merge'
"""
import json
import logging
import sys
from os import path

import click
import requests

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)

GIT_API_URL = 'https://api.github.com/search/issues?per_page=100'


@click.command("get_ready_to_merge_prs")
@click.option(
    '--org',
    help='Org from the GitHub repository URL of https://github.com/<org>/<repo>',
    default='openedx'
)
@click.option(
    '--token',
    envvar='GIT_TOKEN',
    help='The github access token, see https://help.github.com/articles/creating-an-access-token-for-command-line-use/'
)
def get_ready_to_merge_prs(org, token):
    """
    get a list of all prs which are open and have a label "Ready to merge" in organization.

    Args:
        org (str):
        token (str):

    Returns:
            list of all prs.
    """
    urls = get_github_api_response(org, token)
    print(urls)
    return urls


def get_github_api_response(org, token):
    """
    get github pull requests
    https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests
    """
    LOG.info("Preparing to hit api")
    params = f'q=is:pr is:open label:"Ready to merge" org:{org}'
    headers = {
        'Accept': "application/vnd.github.antiope-preview+json",
        'Authorization': "bearer {token}".format(token=token),
    }
    data = []

    try:
        resp = requests.get(GIT_API_URL, params=params, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            LOG.info("Got {count} prs.".format(count=data['total_count']))
            data = [item['html_url'] for item in data['items']]
            data = json.dumps(data)
            return data

        else:
            LOG.error(
                'api return status code {code} and error {con}'.format(code=resp.status_code, con=resp.content)
            )

    except Exception as err:  # pylint: disable=broad-except
        LOG.error('Github api throws error: {con}'.format(con=str(err)))

    return data


def parse_urls(data):
    """
    parse data to return only org, repo and pull request number
    """
    raw_data = data.replace('https://github.com/', '').split('/')
    return raw_data[0], raw_data[1], raw_data[3]


if __name__ == "__main__":
    get_ready_to_merge_prs()  # pylint: disable=no-value-for-parameter
