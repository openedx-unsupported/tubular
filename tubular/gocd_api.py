
"""
Helper API classes for calling GoCD APIs.

https://api.gocd.org/current/
"""
import requests

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

def list_pipeline_group_configs(host, token):
    """
    GoCD get all pipeline group configs
    https://api.gocd.org/current/#pipeline-group-config
    """
    url = f'https://{host}/go/api/admin/pipeline_groups'

    headers = {
        'Accept': 'application/vnd.go.cd.v1+json',
        'Authorization': f'bearer {token}',
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r

def get_pipeline_group_config(host, token, name):
    """
    GoCD get pipeline group configs
    https://api.gocd.org/current/#pipeline-group-config
    """
    url = f'https://{host}/go/api/admin/pipeline_groups/{name}'

    headers = {
        'Accept': 'application/vnd.go.cd.v1+json',
        'Authorization': f'bearer {token}',
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r

def update_pipeline_group_config(host, token, etag, name, data):
    """
    GoCD put pipeline group config
    https://api.gocd.org/current/#pipeline-group-config
    """
    url = f'https://{host}/go/api/admin/pipeline_groups/{name}'

    headers = {
        'Accept': 'application/vnd.go.cd.v1+json',
        'Authorization': "bearer {token}".format(token=token),
        'Content-Type': 'application/json',
        'If-Match': etag,
    }
    r = requests.put(url, json=data, headers=headers)
    r.raise_for_status()
    return r