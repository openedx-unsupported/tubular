The contents of the file titled "discovery-drive.json" are what the google
python API client expects to receive from the google "discovery" API when it
attempts to build a Drive client.  The google python API client does not
actually know what all of the google services are or what their API methods
are, so it literally needs to ask the discovery API first.  The contents of
discovery-drive.json may change over time, but we only use a small subset of
the API methods anyway.

To regenerate this file, for whatever reason, source your venv and try this
script::

    from google.oauth2 import service_account
    from googleapiclient.http import build_http
    from googleapiclient.discovery import _retrieve_discovery_doc
    
    with open('tubular/tests/discovery-drive.json', 'w') as f:
        f.write(_retrieve_discovery_doc('https://www.googleapis.com/discovery/v1/apis/drive/v3/rest', build_http(), False))

