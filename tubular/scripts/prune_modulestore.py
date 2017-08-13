#! /usr/bin/env python3

"""
[WIP]

Command-line script used to clean up (trim) the modulestore structure. By virtue of its nature, the module store
versions updates and over a period of time, these updates account for a significant growth in the size of the
mongo database.

This script prunes the modulestore structures using the parameters specified.

The final product will support:
    1. dry-run:
    2. prune targeted course/active version
    3. prune all active versions
    4. support tests via static data
    5. visualize targeted course trees

Options 2 & 3 support removing all structures or keeping a number of older structures (in support of
user-specified retention policy)

See more details regarding module store at
http://edx.readthedocs.io/projects/edx-developer-guide/en/latest/modulestores/split-mongo.html

See additional details regarding the growth problem with the modulestore at
https://openedx.atlassian.net/browse/PLAT-697

"""

from __future__ import absolute_import
from os import path

import logging
import sys
import click
import click_log

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular import modulestore  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


# parameter handling
@click.command()
@click.option(
    u'--connection',
    default=None,
    help=u'Connection string to the target mongo database. This defaults to localhost without password.'
)
@click.option(
    u'--version-retention',
    default=2,
    help=u'Number of versions to retain for a course/library'
)
@click.option(
    u'--relink-structures',
    default=True,
    help=u'boolean indicator of whether or not to relink the structures to the original version after pruning'
)
@click.option(
    u'--active-version-filter',
    default=None,
    help=u'comma-separated list of objectIds to target for pruning'
)
@click.option(
    u'--database-name',
    default=u'edxapp',
    help=u'name of the edx mongo database containing the course structures to prune'
)
@click_log.simple_verbosity_option(default=u'INFO')
@click_log.init()
def prune_modulestore(
        connection,
        version_retention,
        relink_structures,
        active_version_filter,
        database_name):

    """
    Main script entry point for pruning the edxapp modulestore structures
    """

    # initialize the key variables
    module_store = modulestore.ModuleStore(logger=LOG)
    structure_prune_data = None

    # ensure that version_retention is 2+
    if version_retention < 2:
        raise ValueError("Version retention must be at at least 2: origin and active version")

    # we are using live data
    # establish database connection
    LOG.info("Establishing database connection")
    module_store.initialize_database_connection(
        mongo_database_connection=connection,
        mongo_database_name=database_name)

    # get the data: active versions (courses/library) and accompanying structures
    active_versions = module_store.get_active_versions(active_version_filter)
    LOG.info("{0} active versions identified.".format(len(active_versions)))

    # get the accompanying structures
    filter_enabled = (active_version_filter is not None and len(active_versions) > 0)
    structures = module_store.get_structures(filter_enabled, active_versions)
    LOG.info("{0} associated structure docs identified".format(len(structures)))

    # identify structures that should be deleted
    structure_prune_data = module_store.get_structures_to_delete(
        active_versions,
        structures,
        version_retention,
        relink_structures)

    # prune structures
    structure_prune_candidates = structure_prune_data[u'versions_to_remove']
    LOG.info("{0} structures identified for removal".format(len(structure_prune_candidates)))

    # we are pruning the live data
    module_store.prune_structures(structure_prune_candidates)

    if relink_structures:
        module_store.relink(structures)


if __name__ == '__main__':
    prune_modulestore()  # pylint: disable=no-value-for-parameter
