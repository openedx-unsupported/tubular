#! /usr/bin/env python3

"""
Command-line script to create a release candidate for an application
"""
import io
from os import path
import sys
import logging
import click
import yaml
import requests
import json

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.github_api import GitHubAPI

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


@click.command("get_ready_to_merge_prs")
@click.option(
    '--org',
    help='Org from the GitHub repository URL of https://github.com/<org>/<repo>',
    default='edx'
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
    LOG.info("Getting GitHub token...")

    content = get_github_api_response(org, token)
    if content:
        data = json.loads(content)
        for item in data['items']:
            print(item['html_url'])


def get_github_api_response(org, token):
    """
    get github pull requests
    https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests
    """
    url = 'https://api.github.com/search/issues?'

    params = 'q=is:pr is:open label:"Ready to merge" org:{org}'.format(org=org)
    headers = {
        'Accept': "application/vnd.github.antiope-preview+json",
        'Authorization': "bearer {token}".format(token=token),
    }
    resp = requests.get(url, params=params, headers=headers)
    content = None
    if resp.status_code == 200:
        content = resp.content.decode('utf-8')

    return content

if __name__ == "__main__":
    get_ready_to_merge_prs()  # pylint: disable=no-value-for-parameter
