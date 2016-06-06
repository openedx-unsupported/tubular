#!/usr/bin/env python
import sys
import logging
import traceback
import click
from Crypto.PublicKey import RSA
from os import path

# Add top-level module path to sys.path before importing tubular code.
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )


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
        with open(output_file, 'w') as f:
            f.write(key.exportKey())
    except Exception as e:
        traceback.print_exc()
        click.secho("Error formatting RSA key. \nMessage: {0}".format(e.message), fg='red')
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    format_rsa_key()
