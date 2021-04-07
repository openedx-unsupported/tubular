import unittest
from tubular.kubernetes import check_create_args

new_relic_args = ["source /vault-api-secrets/secrets/secret.env", "newrelic-admin"]
command_args = "while true; do echo still sleeping.; sleep 30; done;"
deployment_args_without_newrelic = ["source /vault-api-secrets/secrets/secret.env && "
                                    "exec gunicorn --workers=2 --name notes"]
deployment_args_with_newrelic = ["source /vault-api-secrets/secrets/secret.env && newrelic-admin run-program"]


class TestCheckArgs(unittest.TestCase):

    def test_args_without_newrelic_cmd(self):
        self.assertEqual(check_create_args(new_relic_args, deployment_args_without_newrelic, command_args), command_args)

    def test_args_with_newrelic_cmd(self):
        self.assertEqual(check_create_args(new_relic_args, deployment_args_with_newrelic, command_args), deployment_args_with_newrelic[0] + " && " + command_args)

