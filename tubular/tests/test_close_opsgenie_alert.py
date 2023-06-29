from unittest import TestCase
from unittest.mock import patch
from click.testing import CliRunner
from ddt import data, ddt, unpack
import json

import tubular.scripts.close_opsgenie_alert as ops

@ddt
class TestCloseOpsgenieAlert(TestCase):
    @unpack
    @data(  # auth-token, alias, source, should_fail
        ('Auth', 'Alias', None, False),
        ('Auth', 'Alias', 'Source', False),
        (None, 'Alias', None, True),
        ('Auth', None, None, True)
    )
    def test_close_alert(self, auth, alias, source, should_fail):
        with patch.object(ops.opsgenie_api.Session, 'post') as mock_post:
            runner = CliRunner()
            args = ['--auth_token', auth, '--alias', alias]
            if source:
                args.extend(['--source', source])
            invoke_response = runner.invoke(
                ops.close_opsgenie_alert,
                catch_exceptions=False,
                args=args,
            )
            if should_fail:
                assert invoke_response.exit_code == 2
        if should_fail:
            mock_post.assert_not_called()
        if not should_fail:
            expected_params = {
                'source': source,
                'note': f"Closed by {source if source else 'OpsGenieAPI'}",
            }
            mock_post.assert_called_once_with(
                url=f"https://api.opsgenie.com/v2/alerts/{alias}/close?identifierType=alias",
                data=json.dumps(expected_params)
            )
