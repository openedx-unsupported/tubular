"""
Cursory tests for config handling in frontend_build.py.

Please note that this suite is NOT currently a comprehensive test
of the frontend build scripts and could use more fleshing out.
"""

from unittest import TestCase, mock

from ..scripts.frontend_build import frontend_build
from ..scripts.frontend_utils import FrontendBuilder

TEST_DATA_DIR = "tubular/tests/example-frontend-config"


class TestFrontendBuildConfigHandling(TestCase):
    """
    Cursory tests for frontend config parsing + marshalling.
    """

    @mock.patch.object(FrontendBuilder, 'create_version_file')
    @mock.patch.object(FrontendBuilder, 'build_app')
    @mock.patch.object(FrontendBuilder, 'install_requirements')
    def test_frontend_build_config_handling(
            self, mock_install, mock_build, mock_create_version
    ):
        exit_code = None
        try:
            frontend_build([
                "--common-config-file",
                f"{TEST_DATA_DIR}/common.yml",
                "--env-config-file",
                f"{TEST_DATA_DIR}/app.yml",
                "--app-name",
                "coolfrontend",
                "--version-file",
                f"{TEST_DATA_DIR}/dummy-path_will-not-get-written.json",
            ])
        except SystemExit as e:
            # We expect this exception to be raised when the Click command
            # completes. The exit code will be 0 if the command was successful.
            exit_code = e.code
        assert exit_code == 0
        assert mock_install.call_count == 1
        assert mock_build.call_count == 1
        assert mock_build.call_args[0][0] == [
            "COMMON_VAR='common_value'",
            "COMMON_OVERRIDE_ME='overriden_value'",
            "VAR_WITH_SINGLE_QUOTES='The // value!'",
            "VAR_WITH_DOUBLE_QUOTES='The // value!'",
            "VAR_WITH_SINGLE_THEN_DOUBLE_QUOTES='The // value!'",
            "VAR_WITH_DOUBLE_THEN_SINGLE_QUOTES=\"The // value!\"",
            "INT='-100'",
            "INT_WITH_QUOTES='-100'",
            "FLOAT='3.14'",
            "FLOAT_WITH_QUOTES='3.14'",
            "BOOL_TRUE='True'",
            "BOOL_TRUE_ANOTHER_WAY='True'",
            "BOOL_TRUE_WITH_QUOTES='True'",
            "BOOL_FALSE='False'",
            "BOOL_FALSE_ANOTHER_WAY='False'",
            "BOOL_FALSE_WITH_QUOTES='False'",
            "NONE='None'",
            "NONE_WITH_QUOTES='None'",
        ]
        assert mock_create_version.call_count == 1
