u"""
Functions for interacting with the Confluence API and for rendering
Confluence pages.
"""

from collections import namedtuple
from enum import Enum
import logging  # pylint: disable=wrong-import-order
import re  # pylint: disable=wrong-import-order

from atlassian.confluence import Confluence  # pylint: disable=import-error

from lxml.html import builder as E
from lxml.html.builder import E as element_maker
import lxml.html

from tubular.github_api import GitHubAPI

SECTION = element_maker.section  # pylint: disable=no-member
VersionDelta = namedtuple(u'VersionDelta', [u'app', u'base', u'new'])


class Version(namedtuple(u'_Version', [u'repo', u'sha'])):
    """
    A value-object capturing a version of a repo.
    """
    __slots__ = ()

    def __lt__(self, other):
        if other is None:
            return False
        else:
            return super().__lt__(other)

    def __le__(self, other):
        if other is None:
            return False
        else:
            return super().__le__(other)

    def __gt__(self, other):
        if other is None:
            return False
        else:
            return super().__gt__(other)

    def __ge__(self, other):
        if other is None:
            return False
        else:
            return super().__ge__(other)


GITHUB_PREFIX = re.compile(u'https?://github.com/')
LOG = logging.getLogger(__name__)


class ReleaseStatus(Enum):
    u"""The set of valid release states."""
    STAGED = u"Deployed to Staging"
    DEPLOYED = u"Deployed to Production"
    ROLLED_BACK = u"Rolled back from Production"


class AMI:
    u"""
    An object capturing details about an AMI.
    """

    def __init__(self, ami_id, environment, deployment, play, **versions):
        self.ami_id = ami_id
        self.environment = environment
        self.deployment = deployment
        self.play = play

        self.versions = {}
        for key, value in versions.items():
            if not key.startswith(u'version:'):
                continue

            _, _, app = key.partition(u':')
            repo, _, sha = value.partition(u' ')
            self.versions[app] = Version(convert_ssh_url(repo), sha)

    def __repr__(self):
        return "{}({!r}, {!r}, {!r}, {!r}, **{!r}".format(
            self.__class__.__name__,
            self.ami_id,
            self.environment,
            self.deployment,
            self.play,
            {
                'version:{}'.format(app): "{} {}".format(version.repo, version.sha)
                for app, version in self.versions.items()
            },
        )


def convert_ssh_url(url):
    u"""
    Convert a git-url for a repository to an https url.
    """
    return url.replace(u'git@github.com:', u'https://github.com/').replace(u'.git', u'')


def version_deltas(base, new):
    u"""
    Yields a list of VersionDelta objects for any changes between `base` and `new`.

    Arguments:
        base, new (AMI): Descriptions of a deployed AMI.
    """
    for app in set(base.versions) | set(new.versions):
        base_version = base.versions.get(app)
        new_version = new.versions.get(app)

        yield VersionDelta(app, base_version, new_version)


def format_commit_url(version):
    """
    Format the url that points to the supplied ``version``.
    """
    return u"{0.repo}/commit/{0.sha}".format(version)


def diff_link(delta):
    u"""
    Return a nicely formatted link that links to a github commit/diff page
    comparing ``delta.base`` and ``delta.new``.
    """
    if delta.base is None:
        summary = u"{} (added)".format(delta.new.sha)
        href = format_commit_url(delta.new)
    elif delta.new is None:
        summary = u"{} (removed)".format(delta.base.sha)
        href = format_commit_url(delta.base)
    elif delta.base.sha == delta.new.sha:
        summary = u"{} (no change)".format(delta.base.sha)
        href = format_commit_url(delta.new)
    else:
        summary = u"{}...{}".format(delta.base.sha, delta.new.sha)
        href = u"{}/compare/{}...{}".format(
            delta.new.repo, delta.base.sha, delta.new.sha
        )

    return [
        u"{} ({}): ".format(
            delta.app,
            GITHUB_PREFIX.sub(u'', (delta.new or delta.base).repo),
        ),
        E.A(summary, href=href),
    ]


def diff(base, new):
    u"""
    Return an Element that renders the version differences between the amis `base` and `new`.

    Arguments:
        base, new (dicts): Descriptions of a deployed AMI. Any keys that start with
            'version:' should have values that are a repo and a sha, separated by a space.
            They must also have the keys 'environment', 'deployment', 'play', and 'ami_id'.
    """
    diff_items = []
    unique_version_changes = set(version_deltas(base, new))
    sorted_version_changes = sorted(unique_version_changes, key=lambda delta: delta.base or delta.new)
    for delta in sorted_version_changes:
        diff_items.append(E.LI(*diff_link(delta)))
    return SECTION(
        E.H3(u"Comparing {base.environment}-{base.deployment}-{base.play}: {base.ami_id} to {new.ami_id}".format(
            base=base,
            new=new,
        )),
        E.UL(*diff_items, style=u"list-style-type: square")
    )


def format_jira_references(jira_url, text):
    u"""
    Return an Element that renders links to all JIRA ticket ids found in `text`.

    Arguments:
        jira_url: The base url that the JIRA tickets should link to.
    """
    if text is None:
        return u""

    tickets = set(re.findall(u"\\b[A-Z]{2,}-\\d+\\b", text))

    if not tickets:
        return u""

    return SECTION(
        *[
            E.P(E.A(ticket, href=u"{}/browse/{}".format(jira_url, ticket)))
            for ticket in sorted(tickets)
        ]
    )


def pr_table(token, jira_url, delta):
    u"""
    Return an Element that renders all changes in `delta` as a table listing merged PRs.abs

    Arguments:
        token: The github token to access the github API with.
        jira_url: The base url of the JIRA instance to link JIRA tickets to.
        delta (VersionDelta): The AMIs to compare.
    """
    version = delta.new or delta.base
    match = re.search(u"github.com/(?P<org>[^/]*)/(?P<repo>.*)", version.repo)
    api = GitHubAPI(match.group(u'org'), match.group(u'repo'), token)

    try:
        prs = api.get_pr_range(delta.base.sha, delta.new.sha)

        change_details = E.TABLE(
            E.CLASS(u"wrapped"),
            E.TBODY(
                E.TR(
                    E.TH(u"Merged By"),
                    E.TH(u"Author"),
                    E.TH(u"Title"),
                    E.TH(u"PR"),
                    E.TH(u"JIRA"),
                    E.TH(u"Release Notes?"),
                ),
                *[
                    E.TR(
                        E.TD(E.A(
                            pull_request.merged_by.login,
                            href=pull_request.merged_by.html_url,
                        )),
                        E.TD(E.A(
                            pull_request.user.login,
                            href=pull_request.user.html_url,
                        )),
                        E.TD(pull_request.title),
                        E.TD(E.A(
                            str(pull_request.number),
                            href=pull_request.html_url,
                        )),
                        E.TD(format_jira_references(jira_url, pull_request.body)),
                        E.TD(u""),
                    )
                    for pull_request in sorted(prs, key=lambda pr: pr.merged_by.login)
                ]
            )
        )
    except Exception:  # pylint: disable=broad-except
        LOG.exception(u'Unable to get PRs for %r', delta)
        change_details = E.P("Unable to list changes")

    return SECTION(
        E.H3(
            u"Changes for {} (".format(delta.app),
            E.A(
                GITHUB_PREFIX.sub(u'', version.repo),
                href=version.repo
            ),
            ")"
        ),
        E.P(
            E.STRONG(u"Before: "),
            E.A(delta.base.sha, href=format_commit_url(delta.base))
        ),
        E.P(
            E.STRONG(u"After: "),
            E.A(delta.new.sha, href=format_commit_url(delta.new))
        ),
        change_details,
    )


class ReleasePage:
    u"""
    An object that captures and renders all of the information needed for a Release Page.
    """

    def __init__(
            self, github_token, jira_url, status, ami_pairs, gocd_url=None,
    ):
        self.github_token = github_token
        self.jira_url = jira_url
        self.gocd_url = gocd_url
        self.status = status
        self.ami_pairs = ami_pairs

    def _format_diffs(self):
        u"""
        Return an Element that contains formatted links to a diff between all AMI pairs.
        """
        return SECTION(
            E.H2(u"Code Diffs"),
            *[
                diff(old, new) for (old, new) in self.ami_pairs
            ]
        )

    def _format_amis(self):
        u"""
        Return an Element that contains formatted description of the deployed AMIs.
        """
        return SECTION(
            E.H2(u"Final AMIs"),
            E.UL(
                *[
                    E.LI(u"{ami.environment}-{ami.deployment}-{ami.play}: {ami.ami_id}".format(ami=ami))
                    for _, ami in self.ami_pairs
                    if ami is not None
                ],
                style=u"list-style-type: square"
            ),
        )

    def _format_changes(self):
        u"""
        Return an Element that contains tables with all merged PRs for each repository that changed.
        """
        deltas = [version_deltas(old, new) for (old, new) in self.ami_pairs]
        tables = [
            pr_table(self.github_token, self.jira_url, delta)
            for delta in sorted(set().union(*deltas), key=lambda delta: delta.base or delta.new)
            if delta.base and delta.new and delta.new.sha != delta.base.sha
        ]
        return SECTION(
            E.H2(u"Detailed Changes"),
            *tables
        )

    def _format_gocd(self):
        u"""
        Return an Element that links to the GoCD build pipeline.
        """
        if self.gocd_url:
            return SECTION(
                E.H2(u"GoCD Release Pipeline"),
                E.A(self.gocd_url, href=self.gocd_url)
            )
        else:
            return None

    def _format_status(self):
        u"""
        Return an Element that renders the current release status.
        """
        return SECTION(
            E.H2(u"Current Status: {}".format(self.status.value))
        )

    def format(self):
        u"""
        Return a formatted JIRA storage-format document representing this release.
        """
        content = [
            self._format_status(),
            self._format_gocd(),
            self._format_diffs(),
            self._format_amis(),
            self._format_changes(),
        ]

        return u"\n".join(
            lxml.html.tostring(piece, pretty_print=True, encoding=u'unicode')
            for piece in content
            if piece is not None
        )


def publish_page(url, user, password, space, title, body, parent_title=None, parent_id=None):
    u"""
    Publish a page to Confluence.

    Arguments:
        url: The base url for the Confluence instance.
        user: The username of the Confluence user to publish as.
        password: The password of the Confluence user.
        space: The space to publish the page into.
        parent_title: The title of the page to make this page a child of.
        title: The title of the page to create.
        body: The storage-format contents of the page to publish.
    """
    conf = Confluence(url, user, password)
    if parent_title is None and parent_id is None:
        raise ValueError("Must pass a parent_title or parent_id")

    if parent_id is None:
        try:
            parent_page = conf.get_page_by_title(space, parent_title)
            parent_id = parent_page[u'id']
        except:
            LOG.error(u'Failed to publish, TITLE: %s BODY: %s', title, body)
            raise ValueError(u"Unable to retrieve page {!r} in space {!r}".format(parent_title, space))
    return conf.update_or_create(parent_id, title, body)
