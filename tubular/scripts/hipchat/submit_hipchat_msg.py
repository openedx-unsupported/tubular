import os
import sys
import requests
import click


HIPCHAT_API_URL = "http://api.hipchat.com"
NOTIFICATION_POST = "/v2/room/{}/notification"
AUTH_HEADER = "Authorization: Bearer {}"


@click.command()
@click.option('--auth_token_env_var', '-a',
              help="Environment variable containing authentication token to use for HipChat REST API.",
              )
@click.option('--channel', '-c',
              default="release pipeline",
              help="Channel to which the script should post a message.",
              )
@click.option('--message', '-m',
              default="Default message.",
              help="Message to send to HipChat channel.",
              )
def cli(auth_token_env_var, channel, message):
    """
    Post a message to a HipChat channel.
    """
    headers = {
        "Authorization": "Bearer {}".format(os.environ[auth_token_env_var])
    }
    msg_payload = {
        "color": "green",
        "message": message,
        "notify": False,
        "message_format": "text"
    }
    post_url = HIPCHAT_API_URL + NOTIFICATION_POST.format(channel)
    r = requests.post(post_url, headers=headers, json=msg_payload)

    # An exit code of 0 means success and non-zero means failure.
    success = r.status_code in (200, 201, 204)
    sys.exit(not success)


if __name__ == '__main__':
    cli()
