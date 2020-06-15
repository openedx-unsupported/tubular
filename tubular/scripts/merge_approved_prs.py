#! /usr/bin/env python3

"""
Command-line script to trigger a jenkins job
"""
from datetime import datetime
import logging
import sys
import os
import os.path

import click
import click_log
import yaml

from tubular import github_api  # pylint: disable=wrong-import-position


def find_approved_prs(target_repo, source_repo, target_base_branch, source_base_branch):
    """
    Yield all PRs in ``target_repo`` which meet the following criteria:
        * have been approved
        * have not been closed
        * have a base branch of ``target_base_branch``
        * have not been merged to ``source_base_branch`` in ``source_repo``

    Arguments:
        target_repo (str, str): A tuple of org, repository
        source_repo (str, str): A tuple of org, repository
        target_base_branch (str): The name of the branch that PRs should be targetting
        source_base_branch (str): The name of a branch that PRs shouldn't have been merged to
    """
    candidate_prs = list(target_repo.find_approved_not_closed_prs(target_base_branch))

    for pull in candidate_prs:
        if not source_repo.has_been_merged(source_base_branch, pull.head.sha):
            yield pull


@click.command()
@click.option(
    '--token',
    help='The github access token, see https://help.github.com/articles/creating-an-access-token-for-command-line-use/',
    required=True,
)
@click.option(
    '--target-repo',
    help='The org, repo pair for the target repository.',
    nargs=2,
    required=True,
)
@click.option(
    '--target-base-branch',
    help='The branch in the target repository that PRs must target.',
    required=True,
)
@click.option(
    '--source-repo',
    help='The org, repo pair of the source repository.',
    nargs=2,
    required=True,
)
@click.option(
    '--source-base-branch',
    help='The branch in the source repository that PRs must not be merged to.',
    required=True,
)
@click.option(
    '--target-branch',
    help='The branch to create in the target repository from the merged PRs.',
    required=True,
)
@click.option(
    '--source-branch',
    help='The branch to merge the approved PRs on top of (from the source repository).',
    required=True,
)
@click.option(
    '--out-file',
    help=u"File location to export metadata about the branches merged to target-branch.",
    type=click.File(mode='w', lazy=True),
    default=sys.stdout,
)
@click.option(
    u'--target-reference-repo',
    help=u"Path to a reference repository to speed up cloning of the target repository",
)
@click.option(
    u'--repo-variable',
    help=u"The name of the variable to add to the results yaml file. This variable will "
         u"contain the url of the repository which has the --sha-variable in it."
)
@click.option(
    u'--sha-variable',
    help=u"The name of the variable to add to the results yaml file. This variable will "
         u"contain the sha of the merge commit.",
    default='merge_sha',
)
@click_log.simple_verbosity_option(default=u'INFO')
@click_log.init()
def octomerge(
        token, target_repo, source_repo, target_base_branch, source_base_branch,
        target_branch, source_branch, out_file, target_reference_repo,
        repo_variable, sha_variable,
):
    u"""
    Merge all approved security PRs into a release candidate.

    Any PR in ``privato-org/target-repo`` will be merged into ``target-branch``, as long
    as the PR meets the following conditions:

        * The PR has been approved (by at least one reviewer)
        * The PR has not been closed
        * The PR has not been merged to ``source-repo-path:source-base-branch``.
        * The PR is targeted at ``target-org/target-repo:target-base-branch``.
    """
    target_github_repo = github_api.GitHubAPI(*target_repo, token=token)
    source_github_repo = github_api.GitHubAPI(*source_repo, token=token)

    with target_github_repo.clone(target_branch, target_reference_repo).cleanup() as local_repo:
        local_repo.add_remote('source', source_github_repo.github_repo.ssh_url)
        local_repo.force_branch_to(target_branch, source_branch, remote='source')

        approved_prs = list(find_approved_prs(
            target_github_repo, source_github_repo, target_base_branch, source_base_branch
        ))
        logging.info("Merging the following prs into {}:\n{}".format(
            target_branch,
            "\n".join(
                "    {.html_url}".format(pr)
                for pr in approved_prs
            )
        ))

        merge_sha = local_repo.octopus_merge(target_branch, (pr.head.sha for pr in approved_prs))
        # The tag encodes the time to ensure that it is a distinct tag.
        release_name = 'release-{date}'.format(date=datetime.now().strftime("%Y%m%d%H%M%S"))
        local_repo.repo.create_tag(
            release_name,
            ref=merge_sha,
        )
        local_repo.push_branch(target_branch, force=True)
        local_repo.push_tags()

        results = {
            'target_branch': target_branch,
            sha_variable: merge_sha,
            'merged_prs': [
                {'html_url': pr.html_url}
                for pr in approved_prs
            ],
        }

        if repo_variable:
            repo = target_github_repo.github_repo

            if repo.private:
                results[repo_variable] = repo.ssh_url
            else:
                results[repo_variable] = repo.clone_url

        dirname = os.path.dirname(out_file.name)
        if dirname:
            os.makedirs(dirname, exist_ok=True)

        yaml.safe_dump(results, stream=out_file)
