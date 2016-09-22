"""
Command-line script to properly format an RSA key.
"""
from __future__ import unicode_literals

import sys
import logging
import traceback
import click
from Crypto.PublicKey import RSA

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


@click.command()
@click.option('--key', help='The RSA key to format as a string', type=str, required=True)
@click.option('--output-file', help='Name of the file to write the newly formated RSA key', required=True)
def format_rsa_key(key, output_file):
    """
    Correctly format the mangled RSA key that is passed from gocd using secure variables
    """
    try:
        key = RSA.importKey(key.decode('unicode_escape'))
        with open(output_file, 'w') as f:  # pylint: disable=open-builtin
            f.write(key.exportKey())
    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho("Error formatting RSA key. \nMessage: {0}".format(err.message), fg='red')
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    format_rsa_key()  # pylint: disable=no-value-for-parameter
