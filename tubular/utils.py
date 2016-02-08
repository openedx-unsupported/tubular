from collections import namedtuple

class TimeoutException(Exception):
    pass

EDC = namedtuple('EDC', ['environment', 'deployment', 'cluster'])

