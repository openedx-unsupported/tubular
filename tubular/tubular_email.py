"""
Convenience functions using boto and AWS SES to send email.
"""

import logging
import backoff
from boto import ses
from tubular.exception import BackendError
from tubular.utils import envvar_get_int

LOG = logging.getLogger(__name__)

# Default maximum number of attempts to send email.
MAX_EMAIL_TRIES_DEFAULT = 10


def _poll_giveup(results):
    """
    Raise an error when the polling tries are exceeded.
    """
    orig_args = results['args']
    msg = 'Timed out after {tries} attempts to send email with subject "{subject}".'.format(
        tries=results['tries'],
        subject=orig_args[3]
    )
    raise BackendError(msg)


@backoff.on_exception(backoff.expo,
                      Exception,
                      max_tries=envvar_get_int("MAX_EMAIL_TRIES", MAX_EMAIL_TRIES_DEFAULT),
                      on_giveup=_poll_giveup)
def _send_email_with_retry(ses_conn,
                           from_address,
                           to_addresses,
                           subject,
                           body):
    """
    Send email, retrying upon exception.
    """
    ses_conn.send_email(
        source=from_address,
        subject=subject,
        body=body,
        to_addresses=to_addresses
    )


def send_email(aws_region,
               from_address,
               to_addresses,
               subject,
               body):
    """
    Send an email via AWS SES using boto with the specified subject/body/recipients.

    Args:
        aws_region (str): AWS region whose SES service will be used, e.g. "us-east-1".
        from_address (str): Email address to use as the From: address. Must be an SES verified address.
        to_addresses (list(str)): List of email addresses to which to send the email.
        subject (str): Subject to use in the email.
        body (str): Body to use in the email - text format.
    """
    ses_conn = ses.connect_to_region(aws_region)
    _send_email_with_retry(
        ses_conn,
        from_address,
        to_addresses,
        subject,
        body
    )
