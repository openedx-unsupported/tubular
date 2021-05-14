
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

def trigger_update_config_repository(host, token):
    """
    Trigger update of config repository
    https://api.gocd.org/current/#trigger-update-of-config-repository
    """
    url = f'https://{host}/go/api/admin/config_repos/config_repo_id/trigger_update'

    headers = {
        'Accept': 'application/vnd.go.cd.v1+json',
        'Authorization': "bearer {token}".format(token=token),
        'X-GoCD-Confirm': 'true',
    }
    r = requests.post(url, json=data, headers=headers)
    # Ignore 409 as it means it is already scheduled.
    if r.status_code not in [409]:
        r.raise_for_status()
    return r

def check_if_config_repo_update_completed(host, token, config_repo_id):
    """
    Status of config repository update
    https://api.gocd.org/current/#status-of-config-repository-update
    """
    url = f'https://{host}/go/api/admin/config_repos/#{config_repo_id}/status'

    headers = {
        'Accept': 'application/vnd.go.cd.v4+json',
        'Content-Type': 'application/vnd.go.cd.v4+json; charset=utf-8',
        'Authorization': "bearer {token}".format(token=token),
        'X-GoCD-Confirm': 'true',
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r