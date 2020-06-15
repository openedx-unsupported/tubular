"""
Tests of tubular.confluence_api.
"""

import textwrap

import pytest
from mock import patch, Mock

try:
    # Attempt to import the atlassian module to see if we can even run these tests.
    import atlassian  # pylint: disable=unused-import
except ImportError:
    AMI = ReleasePage = None
else:
    from tubular.confluence_api import AMI, ReleasePage, ReleaseStatus


@patch(u'tubular.confluence_api.GitHubAPI')
@pytest.mark.skipif(AMI is None, reason=u"Tests require Confluence API")
def test_release_page(mock_github):
    mock_github().get_pr_range.return_value = [
        Mock(
            merged_by=Mock(login=u'user_a', html_url=u'user_html_a'),
            user=Mock(login=u'user_c', html_url=u'user_html_c'),
            title=u'pr a',
            number=1,
            html_url=u'pr_url_1',
            body=u'lorem ipsum TE-1234 TE-4321',
        ),
        Mock(
            merged_by=Mock(login=u'user_b', html_url=u'user_html_b'),
            user=Mock(login=u'user_d', html_url=u'user_html_d'),
            title=u'pr b',
            number=2,
            html_url=u'pr_url_2',
            body=u'lorem ipsum',
        ),
    ]

    page = ReleasePage(
        u'github_token',
        u'jira_url',
        ReleaseStatus.DEPLOYED,
        [
            (
                AMI(
                    u'ami_id_1', u'env', u'depl', u'play',
                    **{
                        u'version:app_a': u'https://github.com/org/repo_a 12345',
                        u'version:app_b': u'https://github.com/org/repo_b 12345',
                    }
                ),
                AMI(
                    u'ami_id_2', u'env', u'depl', u'play',
                    **{
                        u'version:app_a': u'git@github.com:org/repo_a.git 54321',
                        u'version:app_b': u'git@github.com/org/repo_b.git 12345',
                    }
                ),
            )
        ],
        gocd_url=u'gocd_url',
    )

    assert page.format() == textwrap.dedent(u"""\
        <section><h2>Current Status: Deployed to Production</h2></section>

        <section><h2>GoCD Release Pipeline</h2>
        <a href="gocd_url">gocd_url</a></section>

        <section><h2>Code Diffs</h2>
        <section><h3>Comparing env-depl-play: ami_id_1 to ami_id_2</h3>
        <ul style="list-style-type: square">
        <li>app_a (org/repo_a): <a href="https://github.com/org/repo_a/compare/12345...54321">12345...54321</a>
        </li>
        <li>app_b (git@github.com/org/repo_b): <a href="git@github.com/org/repo_b/commit/12345">12345 (no change)</a>
        </li>
        </ul></section></section>

        <section><h2>Final AMIs</h2>
        <ul style="list-style-type: square"><li>env-depl-play: ami_id_2</li></ul></section>

        <section><h2>Detailed Changes</h2>
        <section><h3>Changes for app_a (<a href="https://github.com/org/repo_a">org/repo_a</a>)</h3>
        <p><strong>Before: </strong><a href="https://github.com/org/repo_a/commit/12345">12345</a></p>
        <p><strong>After: </strong><a href="https://github.com/org/repo_a/commit/54321">54321</a></p>
        <table class="wrapped"><tbody>
        <tr>
        <th>Merged By</th>
        <th>Author</th>
        <th>Title</th>
        <th>PR</th>
        <th>JIRA</th>
        <th>Release Notes?</th>
        </tr>
        <tr>
        <td><a href="user_html_a">user_a</a></td>
        <td><a href="user_html_c">user_c</a></td>
        <td>pr a</td>
        <td><a href="pr_url_1">1</a></td>
        <td><section><p><a href="jira_url/browse/TE-1234">TE-1234</a></p>
        <p><a href="jira_url/browse/TE-4321">TE-4321</a></p></section></td>
        <td></td>
        </tr>
        <tr>
        <td><a href="user_html_b">user_b</a></td>
        <td><a href="user_html_d">user_d</a></td>
        <td>pr b</td>
        <td><a href="pr_url_2">2</a></td>
        <td></td>
        <td></td>
        </tr>
        </tbody></table></section></section>
    """)
