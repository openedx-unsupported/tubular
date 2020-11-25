#! /usr/bin/env python3

"""
Command-line script used to update the tag of the legacy gocd agent that is currently being used
"""

import sys
import logging
import traceback
import re
import click
import requests

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


def get_elastic_profile(host, token, profile_id):
    """
    GoCD get elastic profile
    https://api.gocd.org/current/#elastic-agent-profiles
    """
    url = "https://{host}/go/api/elastic/profiles/{profile_id}".format(
        host=host,
        profile_id=profile_id)

    headers = {
        'Accept': 'application/vnd.go.cd.v2+json',
        'Authorization': "bearer {token}".format(token=token),
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r


def put_elastic_profile(host, token, profile_id, etag, data):
    """
    GoCD put elastic profile
    https://api.gocd.org/current/#elastic-agent-profiles
    """
    url = "https://{host}/go/api/elastic/profiles/{profile_id}".format(
        host=host,
        profile_id=profile_id)

    headers = {
        'Accept': 'application/vnd.go.cd.v2+json',
        'Authorization': "bearer {token}".format(token=token),
        'Content-Type': 'application/json',
        'If-Match': etag,
    }
    r = requests.put(url, json=data, headers=headers)
    r.raise_for_status()
    return r


def is_pod_configuration(ep_property):
    """
    Returns true if the key is a pod configuration in
    a GoCD elastic profile ep_property list
    """
    return ep_property['key'] == 'PodConfiguration'


def update_image_in_elastic_profile(host, token, image, tag, profile_id):
    """
    For the specified profile get the pod yaml and replace the tag of any images that
    match with the new tag for a given profile
    """
    response = get_elastic_profile(host, token, profile_id)
    etag = response.headers['etag']
    elastic_profile = response.json()
    pod_configuration_index = next(i for i, v in enumerate(elastic_profile['properties']) if is_pod_configuration(v))
    pod_configuration = elastic_profile['properties'][pod_configuration_index]
    pod_configuration_value = pod_configuration['value']

    # Locate all the image:tag pairs that have the image specified
    # find the tags then replace them with the new tag
    lines = re.findall("^.*image: {image}:.*$".format(image=image), pod_configuration_value, re.MULTILINE)
    for line in lines:
        old_tag = line.split(":", 2)[2]
        pod_configuration_value = pod_configuration_value.replace(old_tag, tag)

    # Now modify the original list since it is copy by value
    elastic_profile['properties'][pod_configuration_index]['value'] = pod_configuration_value
    put_elastic_profile(host, token, profile_id, etag, elastic_profile)


@click.command()
@click.option('--host', help='gocd hostname without protocol eg gocd.tools.edx.org', required=True)
@click.option('--token', help='gocd auth token', required=True)
@click.option('--image', help='image to change the tag on eg: myregistry/myapp', required=True)
@click.option('--tag', help='new tag of the image to replace', required=True)
@click.option('--profile_id', help='new tag of the image to replace', required=True)
def deploy_gocd_legacy_agents(token, host, image, tag, profile_id):
    """
    For the specified profile get the pod yaml and replace the tag of any images that
    match with the new tag for a given profile
    """
    try:
        logging.info("Deploying legacy agent sha: ")
        update_image_in_elastic_profile(host, token, image, tag, profile_id)
    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho('{}'.format(err), fg='red')
        sys.exit(1)

if __name__ == "__main__":
    deploy_gocd_legacy_agents()  # pylint: disable=no-value-for-parameter
