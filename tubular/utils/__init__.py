import os
from collections import namedtuple


WAIT_SLEEP_TIME = int(os.environ.get("WAIT_SLEEP_TIME", 5))

EDP = namedtuple('EDP', ['environment', 'deployment', 'play'])

