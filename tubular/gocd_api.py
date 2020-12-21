""" Commands to interact with the GoCD API. """

import logging
import re
from collections import namedtuple
from datetime import datetime, timedelta
from dateutil import tz

from yagocd import Yagocd as yagocd
from tubular.github_api import default_expected_release_date

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)


class AdvancementPipelineNotFound(Exception):
    """
    Raise when not finding an appropriate advancement pipeline.
    """


class AdvancementPipelineAlreadyAdvanced(Exception):
    """
    Raise when appropriate advancement pipeline has already been advanced.
    """


PipelineInstance = namedtuple('PipelineInstance', ['name', 'counter', 'url'])


class GoCDAPI:
    """
    Interacts with the GoCD API to perform common tasks.
    """

    def __init__(self, username, password, go_server_url):
        self.client = yagocd(
            server=go_server_url,
            auth=(username, password),
        )

    def recent_deployers(
            self,
            pipeline,
            stages,
            cutoff=30,
            email_aliases=None,
            allowed_email_domains=('edx.org',)
    ):
        """
        Return the set of edx emails for users that have changes that have deployed recently.

        Arguments:
            pipeline: The name of the pipeline that does the deployment
            stages: The name of the stages in the pipeline that actually make changes that
                are part of the deployment.
            cutoff: The number of minutes to consider to be "recent" when collecting committers.
            email_aliases: An map of github usernames to groups of emails that are aliases.
            allowed_email_domains: An iterable of email domains that should be returned
        """
        if email_aliases is None:
            email_aliases = {}

        def is_allowed_email(email):
            if not allowed_email_domains:
                return True

            return any(
                email.endswith('@{}'.format(domain))
                for domain in allowed_email_domains
            )

        alias_map = {
            original: {
                alias.lower()
                for alias in alias_group
                if is_allowed_email(alias)
            }
            for alias_group in email_aliases.values()
            for original in alias_group
        }

        for original in list(alias_map.keys()):
            alias_map.setdefault(original.lower(), set()).update(alias_map[original])

        now = datetime.now()
        recent = now - timedelta(minutes=cutoff)

        # Ignore the following repos as changes in them don't go out with deployments
        ignore_repos = [
            'edx-ops/edge-secure',
            'edx-ops/edx-secure',
            'edx/edx-internal',
            'edx/edge-internal',
        ]
        recent_committers = set()
        for pipeline_instance in self.client.pipelines.full_history(pipeline):
            is_recent = any(_is_recent_stage(pipeline_instance, stage, recent) for stage in stages)
            if is_recent:
                recent_committers.update(
                    modification.user_name.lower()
                    for material_revision in pipeline_instance.data.build_cause.material_revisions
                    for modification in material_revision.modifications
                    if material_revision.changed and material_revision.material.type == 'Git' and
                    not any(repo in material_revision.material.description for repo in ignore_repos)
                )
            else:
                break

        recent_commit_emails = {
            re.match('.* <(.*)>', username).group(1)
            for username in recent_committers
            if username is not None
        }

        for email in recent_commit_emails:
            # Match emails like 8483753+crice100@users.noreply.github.com
            match = re.match(r'(\d+\+)?(?P<gh_user>.*)@users.noreply.github.com', email)
            if match:
                alias_map[email] = {
                    alias
                    for alias in email_aliases.get(match.group('gh_user'), ())
                    if is_allowed_email(alias)
                }

        edx_aliased_emails = {
            alias
            for email in recent_commit_emails
            for alias in alias_map.get(email, [email])
        }

        recent_allowed_emails = {
            email for email in edx_aliased_emails
            if is_allowed_email(email)
        }

        LOG.warning("Removed the following non-edX committers: %s", sorted(edx_aliased_emails - recent_allowed_emails))

        return recent_allowed_emails


def _job_trigger_times(stage):
    for job in stage.jobs():
        yield datetime.fromtimestamp(job.data.get('scheduled_date') / 1000)


def _is_recent_stage(pipeline, stage_name, recent):
    """Return whether this stage has triggered within the window defined by recent"""
    stage = pipeline[stage_name]
    if stage is None:
        raise ValueError("{!r} isn't a stage in {}".format(stage_name, pipeline))
    job_trigger_timestamps = _job_trigger_times(stage)
    return any(ts > recent for ts in job_trigger_timestamps)
