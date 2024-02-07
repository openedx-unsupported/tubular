#! /usr/bin/env python3

"""
Command-line script used to update the tag of the legacy gocd agent that is currently being used
"""

import difflib
import logging
import os
import re
import requests
import sys
import traceback

import click
import jinja2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tubular.gocd_api import (  # pylint: disable=wrong-import-position
    get_elastic_profile,
    put_elastic_profile,
)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)

def is_pod_configuration(ep_property):
    """
    Returns true if the key is a pod configuration in
    a GoCD elastic profile ep_property list
    """
    return ep_property['key'] == 'PodConfiguration'


def print_diff(a, b, a_title, b_title):
    """
    Prints a unified diff similar to linux command diff -u
    """

    lines_a = a.splitlines(keepends=True)
    lines_b = b.splitlines(keepends=True)

    print(''.join(difflib.unified_diff(lines_a, lines_b, fromfile=a_title, tofile=b_title)))


def update_image_in_elastic_profile(host, token, profile_id, new_pod_config, apply=False):
    """
    Upload the new_pod_config to the specified profile_id
    """

    assert isinstance(apply, bool)

    response = get_elastic_profile(host, token, profile_id)
    etag = response.headers['etag']
    elastic_profile = response.json()
    pod_configuration_index = next(i for i, v in enumerate(elastic_profile['properties']) if is_pod_configuration(v))
    pod_configuration = elastic_profile['properties'][pod_configuration_index]
    pod_configuration_value = pod_configuration['value']

    logging.info(f"New pod configuration for {profile_id}")
    print(new_pod_config)
    logging.info("Diff of old and new pod configuration")
    print_diff(pod_configuration_value, new_pod_config, f"existing_pod_configuration {profile_id}", f"new_pod_configuration {profile_id}")

    if apply:
      # Now modify the original list since it is copy by value
      logging.info(f"Applying new agent profile {profile_id}")
      elastic_profile['properties'][pod_configuration_index]['value'] = new_pod_config
      put_elastic_profile(host, token, profile_id, etag, elastic_profile)
    else:
      logging.info(f"Not applying new agent profile {profile_id} due to missing --apply flag")


@click.command()
@click.option('--host', help='gocd hostname without protocol eg gocd.tools.edx.org', required=True)
@click.option('--token', help='gocd auth token', required=True)
@click.option('--agent-tag', help='docker image tag of the newly built image to deploy', required=True)
@click.option('--profile-id', required=True, multiple=True,
              help='elastic agent profile to update, mutliple can be specified')
@click.option('--image-name', help='Container image name', default='go-agent')
@click.option('--namespace', help='Kubernetes namespace of the gocd server', default='gocd')
@click.option('--templates-dir', help='Directory holding Jinja2 template files for pod configuration', required=True)
@click.option('--apply', is_flag=True, default=False,
              help='Must be present to actually apply chagnes, otherwise we will only print a diff and exit', required=True)
def configure_gocd_agents(token, host, agent_tag, profile_id, namespace, image_name, templates_dir, apply):
    """
    For the specified profile update the pod yaml with a rendered jina2 templat
    """
    profile_ids = profile_id
    for profile_id in profile_ids:
        j2_environment = jinja2.Environment(
          loader=jinja2.FileSystemLoader(templates_dir)
        )
        j2_template = j2_environment.get_template(f"{profile_id}.yaml.j2")
        new_pod_config = j2_template.render(agent_tag=agent_tag, namespace=namespace, image_name=image_name)
        print(new_pod_config)
        sys.exit(0)
        try:
            logging.info(f"Updating agent profile {profile_id} with agent image tag {agent_tag}")
            update_image_in_elastic_profile(host, token, profile_id, new_pod_config, apply)
        except Exception as err:  # pylint: disable=broad-except
            traceback.print_exc()
            click.secho('{}'.format(err), fg='red')
            sys.exit(1)

if __name__ == "__main__":
    configure_gocd_agents()  # pylint: disable=no-value-for-parameter
