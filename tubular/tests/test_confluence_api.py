"""
Tests of tubular.confluence_api.
"""

import textwrap

from unittest.mock import patch, Mock
import pytest

try:
    # Attempt to import the atlassian module to see if we can even run these tests.
    import atlassian  # pylint: disable=unused-import
except ImportError:
    AMI = ReleasePage = None
else:
    from tubular.confluence_api import AMI, ReleasePage, ReleaseStatus


@patch('tubular.confluence_api.GitHubAPI')
@pytest.mark.skipif(AMI is None, reason="Tests require Confluence API")
def test_release_page(mock_github):
    mock_github().get_pr_range.return_value = [
        Mock(
            merged_by=Mock(login='user_a', html_url='user_html_a'),
            user=Mock(login='user_c', html_url='user_html_c'),
            title='pr a',
            number=1,
            html_url='pr_url_1',
            body='lorem ipsum TE-1234 TE-4321',
        ),
        Mock(
            merged_by=Mock(login='user_b', html_url='user_html_b'),
            user=Mock(login='user_d', html_url='user_html_d'),
            title='pr b',
            number=2,
            html_url='pr_url_2',
            body='lorem ipsum',
        ),
    ]

    page = ReleasePage(
        'github_token',
        'jira_url',
        ReleaseStatus.DEPLOYED,
        [
            (
                AMI(
                    'ami_id_1', 'env', 'depl', 'play',
                    **{
                        'version:app_a': 'https://github.com/org/repo_a 12345',
                        'version:app_b': 'https://github.com/org/repo_b 12345',
                    }
                ),
                AMI(
                    'ami_id_2', 'env', 'depl', 'play',
                    **{
                        'version:app_a': 'git@github.com:org/repo_a.git 54321',
                        'version:app_b': 'git@github.com/org/repo_b.git 12345',
                    }
                ),
            )
        ],
        gocd_url='gocd_url',
    )

    assert page.format() == textwrap.dedent("""\
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
