"""
Script to submit an event to Segment.
"""

from os import path
import sys
import base64
import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.segment_api import SegmentApi  # pylint: disable=wrong-import-position

@click.command("send_segment_event")
@click.option(
    '--authToken',
    required=True,
    help="Segment write token",
)
@click.option(
    '--eventName',
    required=True,
    help="Name of the event to send to Segment",
)
@click.option(
    '--properties',
    required=False,
    help="Properties dictionary for the event to send to Segment",
)

def send_segment_event(authToken, eventName, properties):
    """
    Sends an event to segmment.
    """
    baseUrl = 'https://api.segment.io/'
    workSpaceSlug = 'edx'
    encodedAuthToken = base64.b64encode("{}:".format(authToken))
    segment_api = SegmentApi(baseUrl,
    encodedAuthToken, workSpaceSlug)
    segment_api.send_event_to_segment(eventName, properties)
    # An exit code of 0 means success and non-zero means failure.
    sys.exit(0)

if __name__ == '__main__':
    send_segment_event()  # pylint: disable=no-value-for-parameter
