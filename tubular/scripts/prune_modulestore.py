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

import json
import logging
import os
import sys
import click
import click_log
from bson.objectid import ObjectId
from pymongo import MongoClient

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)

# the dictionary keys to track for active versions
TARGET_ACTIVE_VERSIONS_KEYS = [u'library', u'draft-branch', u'published-branch']


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
    default=False,
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
    help=u'name of the edx database to prune'
)
@click.option(
    u'--test-data-file',
    default=None,
    help=u'file path containing a json representation of test data to use for pruning validation'
)
@click.option(
    u'--output-file',
    default=u'pruned_dataset.json',
    help=u'output file of the prune structures for test purposes'
)
@click_log.simple_verbosity_option(default=u'DEBUG')
@click_log.init()
def prune_modulestore(
        connection,
        version_retention,
        relink_structures,
        active_version_filter,
        database_name,
        test_data_file,
        output_file):

    """
    Main script entry point for pruning the edxapp modulestore structures
    """

    # initialize the key variables
    db_client = None
    structure_prune_data = None
    testmode_data = None
    operation_status = 0

    # ensure that version_rention 2+
    if version_retention < 2:
        raise ValueError("Version rention must be at at least 2: origin and active version")

    # Support loading sample dataset from file system for test purposes
    if test_data_file is not None:

        LOG.debug("Test Mode Detected: loading datasets from '{0}'".format(test_data_file))

        # load the test data
        testmode_data = load_test_dataset(test_data_file)

        # we are using test data
        active_versions = testmode_data[u'active_versions']
        structures = testmode_data[u'structures']

    else:
        # we are using live data
        # establish database connection
        LOG.debug("Establishing database connection")
        db_client = get_database(connection, database_name)

        # get the data: active versions (courses/library) and accompanying structures
        # get a dictionary listing all active versions
        active_versions = get_active_versions(db_client, active_version_filter)
        LOG.debug("{0} active versions identified.".format(len(active_versions)))

        # get the accompanying structures
        filter_enabled = (active_version_filter is not None and len(active_versions) > 0)
        structures = get_structures(db_client, filter_enabled, active_versions)
        LOG.debug("{0} associated structure docs identified".format(len(structures)))

    # identify structures that should be deleted
    structure_prune_data = get_structures_to_delete(active_versions,
                                                    structures,
                                                    version_retention,
                                                    relink_structures)

    # prune structures
    structure_prune_candidates = structure_prune_data[u'versions_to_remove']
    LOG.debug("{0} structures identified for removal".format(len(structure_prune_candidates)))

    if test_data_file is not None:

        # we are pruning the static data instead of the database
        pruned_dataset = prune_structures_static_data(testmode_data, structure_prune_candidates)

        if relink_structures:
            pruned_dataset[u'structures'] = relink(None, pruned_dataset[u'structures'])

        # save the output
        save_data_file(pruned_dataset, output_file)

        operation_status = 1

    else:

        # we are pruning the live data
        prune_structures(db_client, structure_prune_candidates)

        if relink_structures:
            relink(db_client, structures)

        operation_status = 1

    # An exit code of 0 means success and non-zero means failure.
    return operation_status


###################################
# Support functions
###################################

def save_data_file(data, output_file):

    """
    Save the specified data file to disk
    """

    LOG.debug("Saving the purged dataset to {0}".format(output_file))

    # write the updated dataset
    with open(output_file, 'w') as outfile:
        json.dump(data, outfile)


def prune_structures_static_data(original_dataset, structures_to_remove):

    """
    Prune the static test data and return the results
    """

    pruned_static_data = []

    for structure_doc in original_dataset[u'structures']:

        if structure_doc[u'_id'] not in structures_to_remove:
            pruned_static_data.append(structure_doc)

    original_dataset[u'structures'] = pruned_static_data

    return original_dataset


def load_test_dataset(dataset_file):

    """
    Load the json dataset from the file specified
    """

    # check if the specified file exists
    file_exists = os.path.isfile(dataset_file)

    assert isinstance(file_exists, object)
    if not file_exists:
        raise IOError("The specified file doesn't exist: {0}".format(dataset_file))

    # load the file
    with open(dataset_file) as dataset:
        data = json.load(dataset)

    return data


def get_query_filter(doc_filter):

    """
    Generate a document filter for bulk querying
    """

    # establish the query filter  (respecting cases where no value is specified)
    query_filter = None

    if len(doc_filter['$in']) > 0:
        query_filter = {"_id": doc_filter}

    return query_filter


def get_active_version_filter(active_version_id_list):

    """
    Generate document filter for bulk querying the active version collection
    """

    av_filter = {'$in': []}

    for active_version_id in active_version_id_list.split(","):
        av_filter['$in'].append(ObjectId(active_version_id.strip()))

    # establish the query filter  (respecting cases where no value is specified)
    return get_query_filter(av_filter)


def get_structures_filter(active_version_list):

    """
    Generate document filter for bulk querying the structures collection
    """

    structure_filter = {'$in': []}

    for active_version in active_version_list:

        for target_key in TARGET_ACTIVE_VERSIONS_KEYS:
            if target_key in active_version['versions']:
                structure_filter['$in'].append(ObjectId(active_version['versions'][target_key]))

    # establish the query filter  (respecting cases where no value is specified)
    return get_query_filter(structure_filter)


def get_active_versions(db, active_version_list=None):

    """
    Get all documents from the active_versions collection
    """

    # establish the active version filter (if required)
    active_version_filter = None

    if active_version_list is not None:
        active_version_filter = get_active_version_filter(active_version_list)

    fields = {
        "versions.draft-branch": 1,
        "versions.published-branch": 1,
        "versions.library": 1,
    }

    # initialize our active versions dictionary
    active_versions = []

    # TODO: apply filters here in support of a user limiting the pruning operation to 1+ course/active versions
    if active_version_filter is None:
        resultset = db.modulestore.active_versions.find({}, fields)
    else:
        resultset = db.modulestore.active_versions.find(active_version_filter, fields)

    for active_version_doc in resultset:

        # collect all interesting docs: library & [draft|published]-branch active versions
        avdocs_versions = active_version_doc['versions']

        if u'library' in avdocs_versions \
                or u'draft-branch' in avdocs_versions \
                or u'published-branch' in avdocs_versions:
            active_versions.append(active_version_doc)

    # return the active versions
    return active_versions


def get_structures(db, filter_enabled, active_versions_list):

    """
    Get all documents from the structures collection
    """

    # use filters (if required)
    structure_filter = None
    if filter_enabled:
        structure_filter = get_structures_filter(active_versions_list)

    fields = {
        "_id": 1,
        "previous_version": 1,
        "original_version": 1
    }

    structures_list = []

    # TODO: apply filters to support limiting the pruning operation to 1 or more courses / active versions
    if structure_filter is None:
        resultset = db.modulestore.structures.find({}, fields)
    else:
        resultset = db.modulestore.structures.find(structure_filter, fields)

    for structure_doc in resultset:

        # Get a list of all structures (or those relevant to the active versions via specified filter)
        # this will give the list of Dictionary's with _id and previous_version
        structures_list.append(structure_doc)

    return structures_list


def prune_structures(db, structures_to_remove):

    """
    Prune the specified documents from the structures collection
    """

    # TODO: (performance): chunk up the removals to minimize possible production impact
    if len(structures_to_remove) == 0:
        return

    structures_removal_filter = {'$in': []}

    for structure_objectid_str in structures_to_remove:
        structures_removal_filter['$in'].append(ObjectId(structure_objectid_str))

    return db.modulestore.structures.remove({'_id': structures_removal_filter})


# TODO: get this fully operational. Test against static data is ready.
def relink(db, structures):

    """
    There are ongoing discussions about the need to support relinking modulestore structures
    to their original version.

    Keeping this as a place holder.

    """

    LOG.debug("Relinking structure to original version")

    index_position = 0
    available_ids = []

    # build a list of all available ids
    available_ids.extend([structure_doc['_id'] for structure_doc in structures])

    # iterate structures and relink to original
    for structure_doc in structures:

        if structure_doc["previous_version"] is not None and structure_doc["previous_version"] not in available_ids:

            LOG.debug("{0} was not found in {1}".format(structure_doc["previous_version"], available_ids))

            to_be_linked_version_id = []
            original_version_id = []

            to_be_linked_version_id.append(structure_doc['_id'])
            original_version_id.append(structure_doc['original_version'])

            LOG.debug("{0} version is being linked to {1}".format(to_be_linked_version_id, original_version_id[0]))

            # TODO: refactor to support bulk updates for performance concerns
            if db is not None:

                # this is a live update session
                db.modulestore.structures.update(
                    {'_id': {'$in': to_be_linked_version_id}},
                    {'$set': {"previous_version": original_version_id[0]}})

            else:

                # this is working against static dataset
                structures[index_position][u'previous_version'] = original_version_id[0]

        else:
            LOG.debug("Nothing to link for structure: {0}".format(structure_doc['_id']))

        # advance the index position
        index_position += 1

    return structures


def find_previous_version(lookup_key, lookup_value, structures_list):

    """
    This function searches all structure documents for the one specified
    """

    # it is more efficient to use a structures list
    # instead of separate db calls (which may be necessary for supporting
    # pruning individual active versions)
    for structure_doc in structures_list:

        if structure_doc[lookup_key] == lookup_value:
            return structure_doc


def build_activeversion_tree(active_version, structures):

    """
    Build a tree representing the active_version and its tree of ancestors
    from structures
    """

    # link the active version to its base version in structures
    structure_doc = find_previous_version('_id', active_version, structures)

    # map the tree for the identified structure
    version_tree = []

    # recursively identify the ancestors
    if structure_doc is not None:

        # build the tree
        version_tree.append(str(structure_doc['_id']))

        while structure_doc[u'previous_version'] is not None:

            # search for the parent structure doc
            structure_doc = find_previous_version('_id', structure_doc[u'previous_version'], structures)

            # build the tree - recursively
            if structure_doc is None:
                # end of the tree (original version)
                break

            version_tree.append(str(structure_doc['_id']))

    return version_tree


def get_structures_to_delete(active_versions, structures=None, version_retention=2, relink_structures=False):

    """
    Generate a list of structures that meet the conditions for pruning and associated visualization
    """

    # initialize key variables
    version_trees = []
    versions_to_retain = []
    versions_to_remove = []
    counter = 0

    # iterate the active versions and build the associated version tree
    for active_version in active_versions:

        counter += 1

        for target_key in TARGET_ACTIVE_VERSIONS_KEYS:

            if target_key in active_version['versions']:

                # print(active_version)
                version_tree = build_activeversion_tree(active_version['versions'][target_key], structures)

                # only add the tree if it has 1+ element
                tree_length = len(version_tree)
                if tree_length > 0:

                    status_message = "Processing Active Version {0} | {3}: {1} version with a {2}-version tree"

                    LOG.debug(status_message.format(
                        counter,
                        target_key,
                        len(version_tree),
                        str(active_version['_id'])))

                    # if the tree exceeds the minimum number of elements,
                    # identify tree elements that should be removed
                    if tree_length > version_retention:

                        # track the required version: first & last
                        versions_to_retain.extend(version_tree[:2])

                        # if relinking is not required, it is ok to remove the original version
                        if not relink_structures:
                            versions_to_retain.append(version_tree[-1])

                        # This will extract the mid range of 1 to n+1 version id's from the version_tree
                        versions_to_remove.extend(version_tree[version_retention - 1: len(version_tree) - 1])

                        # tree mapping is complete, add to forest/list of trees
                    # only useful for dry runs and graphing purposes
                    version_trees.append(version_tree)

    # All trees have been processed.
    # We now have a final list of structures to retain & remove

    # remove duplicates from the versions_to_retain
    versions_to_retain = list(set(versions_to_retain))

    # remove structures on the versions_to_remove list that are on the versions_to_retain list
    # this supports course re-runs and related links
    versions_to_remove = list(set(versions_to_remove) - set(versions_to_retain))

    # return the list of items to remove
    return {'versions_to_remove': versions_to_remove, 'version_trees': version_trees}


def get_database(connection, database_name):

    """
    Establish a connection to the database
    """

    if connection is None:
        client = MongoClient()
    else:
        client = MongoClient(connection)

    return client[database_name]


if __name__ == '__main__':
    prune_modulestore()  # pylint: disable=no-value-for-parameter
