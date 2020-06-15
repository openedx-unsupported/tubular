#! /usr/bin/env python3

"""
Command-line script to create a PR moving any merged changes from a tracking branch in a private repo
into a branch being tracked in a public repo. Used to automate the merging of security fixes from a
private repo into a public repo.
"""

import io
from os import path
import sys
import logging
import yaml
import click
import click_log

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.git_repo import LocalGitAPI  # pylint: disable=wrong-import-position
from tubular.github_api import GitHubAPI, PullRequestCreationError  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


@click.command()
@click.option(
    u'--private_org',
    help=u'Org from the private GitHub repository URL of https://github.com/<org>/<repo>',
    default=u'edx'
)
@click.option(
    u'--private_repo',
    help=u'Repo name from the private GitHub repository URL of https://github.com/<org>/<repo>'
)
@click.option(
    u'--private_source_branch',
    help=u'Source branch from the private repo to be merged into the target branch of the public repo in the PR.',
    required=True
)
@click.option(
    u'--public_org',
    help=u'Org from the public GitHub repository URL of https://github.com/<org>/<repo>',
    default=u'edx'
)
@click.option(
    u'--public_repo',
    help=u'Repo name from the public GitHub repository URL of https://github.com/<org>/<repo>'
)
@click.option(
    u'--public_target_branch',
    help=u'Target base branch from the public repo into which the private source branch will be merged in the PR.',
    required=True
)
@click.option(
    '--token',
    envvar='GIT_TOKEN',
    help='The github access token, see https://help.github.com/articles/creating-an-access-token-for-command-line-use/'
)
@click.option(
    u'--output_file',
    help=u'File in which to write the script\'s YAML output',
)
@click.option(
    u'--reference_repo',
    help=u'Path to a reference private repo to use to speed up repo cloning.',
)
@click_log.simple_verbosity_option(default=u'INFO')
@click_log.init()
def create_private_to_public_pr(private_org,
                                private_repo,
                                private_source_branch,
                                public_org,
                                public_repo,
                                public_target_branch,
                                token,
                                output_file,
                                reference_repo):
    u"""
    Creates a PR to merge the private source branch into the public target branch.
    Clones the repo in order to perform the proper git commands locally.
    """
    public_github_url = u'git@github.com:{}/{}.git'.format(public_org, public_repo)
    private_github_url = u'git@github.com:{}/{}.git'.format(private_org, private_repo)
    output_yaml = {
        u'private_github_url': private_github_url,
        u'private_source_branch_name': private_source_branch,
        u'public_github_url': public_github_url,
        u'public_target_branch_name': public_target_branch
    }

    LOG.info('Cloning private repo %s with branch %s.', private_github_url, private_source_branch)
    with LocalGitAPI.clone(private_github_url, private_source_branch, reference_repo).cleanup() as local_repo:
        # Add the public repo as a remote for the private git working tree.
        local_repo.add_remote('public', public_github_url)
        # Create a new public branch with unique name.
        new_branch_name = 'private_to_public_{}'.format(local_repo.get_head_sha()[:7])
        # Push the private branch into the public repo.
        LOG.info(
            'Pushing private branch %s to public repo %s as branch %s.',
            private_source_branch, public_github_url, new_branch_name
        )
        local_repo.push_branch(private_source_branch, 'public', new_branch_name)
        github_api = GitHubAPI(public_org, public_repo, token)
        # Create a PR from new public branch to public master.
        try:
            pull_request = github_api.create_pull_request(
                title='Mergeback PR from private to public.',
                body='Merge private changes back to the public repo post-PR-merge.\n\n'
                     'Please review and tag appropriate parties.',
                head=new_branch_name,
                base=public_target_branch
            )
        except PullRequestCreationError as exc:
            LOG.info(
                "No pull request created for merging %s into %s in '%s' repo - nothing to merge: %s",
                new_branch_name,
                public_target_branch,
                public_github_url,
                exc
            )
            output_yaml.update({
                'pr_created': False,
            })
            # Cleanup - delete the pushed branch.
            github_api.delete_branch(new_branch_name)
        else:
            LOG.info('Created PR #%s for repo %s: %s', pull_request.number, public_github_url, pull_request.html_url)
            output_yaml.update({
                'pr_created': True,
                'pr_id': pull_request.id,
                'pr_number': pull_request.number,
                'pr_url': pull_request.url,
                'pr_repo_url': github_api.github_repo.url,
                'pr_head': pull_request.head.sha,
                'pr_base': pull_request.base.sha,
                'pr_html_url': pull_request.html_url,
                'pr_diff_url': pull_request.diff_url,
                'pr_mergable': pull_request.mergeable,
                'pr_state': pull_request.state,
                'pr_mergable_state': pull_request.mergeable_state,
            })

    if output_file:
        with io.open(output_file, u'w') as stream:
            yaml.safe_dump(
                output_yaml,
                stream,
                default_flow_style=False,
                explicit_start=True
            )
    else:
        yaml.safe_dump(
            output_yaml,
            sys.stdout,
        )


if __name__ == u"__main__":
    create_private_to_public_pr()  # pylint: disable=no-value-for-parameter
