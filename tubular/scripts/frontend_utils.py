"""
Utility file with helper classes for building and deploying frontends. Keeps
single and multi deployment scripts DRY.
"""
import io
import json
import os
import subprocess
import sys
from datetime import datetime
from functools import partial

import CloudFlare
import backoff
import yaml
from git import Repo

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tubular.git_repo import LocalGitAPI  # pylint: disable=wrong-import-position
from tubular.scripts.helpers import _log, _fail  # pylint: disable=wrong-import-position

MAX_TRIES = 3


class FrontendBuilder:
    """ Utility class for building frontends. """
    SCRIPT_SHORTNAME = 'Build frontend'
    LOG = partial(_log, SCRIPT_SHORTNAME)
    FAIL = partial(_fail, SCRIPT_SHORTNAME)

    def __init__(self, common_config_file, env_config_file, app_name, version_file):
        self.common_config_file = common_config_file
        self.env_config_file = env_config_file
        self.app_name = app_name
        self.version_file = version_file
        self.common_cfg, self.env_cfg = self._get_configs()

    def _get_configs(self):
        """Loads configs from their paths"""
        try:
            with io.open(self.common_config_file, 'r') as contents:
                common_vars = yaml.safe_load(contents)
        except IOError:
            self.FAIL(1, 'Common config file could not be opened.')

        try:
            with io.open(self.env_config_file, 'r') as contents:
                env_vars = yaml.safe_load(contents)
        except IOError:
            self.FAIL(1, 'Environment config file could not be opened.')

        return (common_vars, env_vars)

    def install_requirements(self):
        """ Install requirements for app to build """
        proc = subprocess.Popen(['npm install'], cwd=self.app_name, shell=True)
        return_code = proc.wait()
        if return_code != 0:
            self.FAIL('Could not run `npm install` for app {}.'.format(self.app_name))

        self.install_requirements_npm_aliases()

    def install_requirements_npm_aliases(self):
        """ Install npm alias requirements for app to build """
        npm_aliases = self.get_npm_aliases_config()
        if npm_aliases:
            # Install the latest version of npm that supports aliases (>= 6.9.0)
            proc = subprocess.Popen(['npm install npm'], cwd=self.app_name, shell=True)
            return_code = proc.wait()
            if return_code != 0:
                self.FAIL('Could not run `npm install npm` for app {}.'.format(self.app_name))

            aliased_installs = ' '.join(['{}@{}'.format(k, v) for k, v in npm_aliases.items()])
            # Use the locally installed npm at ./node_modules/.bin/npm
            install_aliases_proc = subprocess.Popen(
                ['./node_modules/.bin/npm install {}'.format(aliased_installs)],
                cwd=self.app_name,
                shell=True
            )
            install_aliases_proc_return_code = install_aliases_proc.wait()
            if install_aliases_proc_return_code != 0:
                self.FAIL('Could not run `npm install` aliases {} for app {}.'.format(
                    aliased_installs, self.app_name
                ))

    def get_app_config(self):
        """ Combines the common and environment configs APP_CONFIG data """
        app_config = self.common_cfg.get('APP_CONFIG', {})
        app_config.update(self.env_cfg.get('APP_CONFIG', {}))
        if not app_config:
            self.LOG('Config variables do not exist for app {}.'.format(self.app_name))
        return app_config

    def get_npm_aliases_config(self):
        """ Combines the common and environment configs NPM_ALIASES data """
        npm_aliases_config = self.common_cfg.get('NPM_ALIASES', {})
        npm_aliases_config.update(self.env_cfg.get('NPM_ALIASES', {}))
        if not npm_aliases_config:
            self.LOG('No npm package aliases defined in config.')
        return npm_aliases_config

    def build_app(self, env_vars, fail_msg):
        """ Builds the app with environment variable."""
        proc = subprocess.Popen(
            ' '.join(env_vars + ['npm run build']),
            cwd=self.app_name,
            shell=True
        )
        build_return_code = proc.wait()
        if build_return_code != 0:
            self.FAIL(1, fail_msg)

    def create_version_file(self):
        """ Creates a version.json file to be deployed with frontend """
        # Add version.json file to build.
        version = {
            'repo': self.app_name,
            'commit': LocalGitAPI(Repo(self.app_name)).get_head_sha(),
            'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        try:
            with io.open(self.version_file, 'w') as output_file:
                json.dump(version, output_file)
        except IOError:
            self.FAIL(1, 'Could not write to version file for app {}.'.format(self.app_name))


class FrontendDeployer:
    """ Utility class for deploying frontends. """

    SCRIPT_SHORTNAME = 'Deploy frontend'
    LOG = partial(_log, SCRIPT_SHORTNAME)
    FAIL = partial(_fail, SCRIPT_SHORTNAME)

    def __init__(self, env_config_file, app_name):
        self.env_config_file = env_config_file
        self.app_name = app_name
        self.env_cfg = self._get_config()

    def _get_config(self):
        """Loads config from it's path"""
        try:
            with io.open(self.env_config_file, 'r') as contents:
                env_vars = yaml.safe_load(contents)
        except IOError:
            self.FAIL(1, 'Environment config file {} could not be opened.'.format(self.env_config_file))
        return env_vars

    def deploy_site(self, bucket_name, app_path):
        """Deploy files to bucket."""
        bucket_uri = 's3://{}'.format(bucket_name)
        proc = subprocess.Popen(
            ' '.join(['aws s3 sync', app_path, bucket_uri, '--delete']),
            shell=True
        )
        return_code = proc.wait()
        if return_code != 0:
            self.FAIL(1, 'Could not sync app {} with S3 bucket {}.'.format(self.app_name, bucket_uri))
        self.LOG('Frontend application {} successfully deployed to {}.'.format(self.app_name, bucket_name))

    @backoff.on_exception(backoff.expo,
                          (CloudFlare.exceptions.CloudFlareAPIError),
                          max_tries=MAX_TRIES)
    def purge_cache(self, bucket_name):
        """
            Purge the Cloudflare cache for the frontend hostname.
            Frontend S3 buckets are named by hostname.
            Cloudflare zones are named by domain.
            Assumes the caller's shell has the following environment
            variables set to enable Cloudflare API auth:
            CF_API_EMAIL
            CF_API_KEY
        """
        zone_name = '.'.join(bucket_name.split('.')[-2:])  # Zone name is the TLD
        data = {'hosts': [bucket_name]}
        cloudflare_client = CloudFlare.CloudFlare()
        zone_id = cloudflare_client.zones.get(params={'name': zone_name})[0]['id']  # pylint: disable=no-member
        cloudflare_client.zones.purge_cache.post(zone_id, data=data)  # pylint: disable=no-member
        self.LOG('Successfully purged Cloudflare cache for hostname {}.'.format(bucket_name))
