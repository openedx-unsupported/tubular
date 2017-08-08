#! /usr/bin/env python3

"""
[WIP]

Command-line script used to clean up (trim) the modulestore structure. By virtue of its nature, the module store versions updates and over a period of time, these updates account for a significant growth in the size of the mongo database.abs

This script supports:
    1. dry-run:
    2. prune targeted course/active version
    3. prune all active versions

Options 2 & 3 support removing all structures or keeping a number of older structures (in support of user-specified retention policy)

See more details regarding module store at http://edx.readthedocs.io/projects/edx-developer-guide/en/latest/modulestores/split-mongo.html
See additional details at https://openedx.atlassian.net/browse/PLAT-697
"""

# pylint: disable=invalid-name
from __future__ import absolute_import

from os import path
from pymongo import MongoClient
from bson.objectid import ObjectId

import click
import click_log
import logging
import sys
import time
import traceback

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
    u'--relink-original', 
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
@click_log.simple_verbosity_option(default=u'DEBUG')
@click_log.init()
def prune_modulestore(connection, version_retention, relink_original, active_version_filter, database_name):
    
    # ensure that version_rention 2+
    if version_retention < 2:
        raise ValueError("Version rention must be at at least 2: origin and active version")

    # TODO: enable support for loading sample dataset from file system 
    # for test purposes
    
    # establish database connection
    LOG.debug("Establishing database connection")
    db_client = get_database(connection, database_name)

    # get the data: active versions (courses/library) and accompanying structures
    # get a dictionary listing all active versions
    active_versions = get_active_versions(db_client, active_version_filter)
    LOG.debug("{0} active versions identified.".format(len(active_versions)))
    
    # get the accompanying structures
    start = time.time()
    filter_enabled = (active_version_filter is not None and len(active_versions) > 0)
    structures = get_structures(db_client, filter_enabled, active_versions)
    end = time.time()
    LOG.debug("{0} associated structure docs identified. Duration={1}".format(len(structures), (end - start)))

    # identify structures that should be deleted
    try:
        structure_prune_data = get_structures_to_delete(active_versions, structures, db_client, version_retention)        
    except:
        print("Error occurred while processing structures to delete:", sys.exc_info()[1])
        traceback.print_exc(limit=4, file=sys.stdout)
        

    # prune structures
    structure_prune_candidates = structure_prune_data[u'versions_to_remove']
    LOG.debug("{0} structures identified for removal".format(len(structure_prune_candidates)))

    try:
        prune_structures(db_client, structure_prune_candidates)
        
        if relink_original == True:
            relink(db, structures)

        status_success = 1

    except:
        print("Error pruning the database:", sys.exc_info()[1])
        traceback.print_exc(limit=4, file=sys.stdout)

    # An exit code of 0 means success and non-zero means failure.
    sys.exit(not status_success)

###################################333
# Support functions 
###################################333

def get_query_filter(doc_filter):

    """
    Generate a document filter for bulk querying
    """
    
    # establish the query filter  (respecting cases where no value is specified)
    query_filter = None

    if len(doc_filter['$in']) > 0:
        query_filter = { '_id' : doc_filter }

    return query_filter

def get_active_version_filter(active_version_id_list):

    """
    Generate document filter for bulk querying the active version collection
    """

    av_filter = { '$in' : [] }

    for active_version_id in active_version_id_list.split(","):
        av_filter['$in'].append(ObjectId(active_version_id.strip()))

    # establish the query filter  (respecting cases where no value is specified)
    return get_query_filter(av_filter)

def get_structures_filter(active_version_list):

    """
    Generate document filter for bulk querying the structures collection
    """

    structure_filter = { '$in' : [] }

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

    # Initializing the empty lists
    required_version_list = []

    fields = {
        "versions.draft-branch": 1, 
        "versions.published-branch": 1,
        "versions.library": 1, 
    }

    # initialize our active versions dictionary
    active_versions = []

    # TODO: apply filters here in support of a user limiting the 
    # pruning operation to 1 or more courses / active versions
    if active_version_filter is None:
        resultset = db.modulestore.active_versions.find({}, fields)
    else:
        resultset = db.modulestore.active_versions.find(active_version_filter, fields)

    for active_version_doc in resultset:

        # collect all interesting docs: library & [draft|published]-branch active versions
        avdocs_versions = active_version_doc['versions']

        if u'library' in avdocs_versions or u'draft-branch' in avdocs_versions or u'published-branch' in avdocs_versions:
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
    
    # TODO: apply filters here in support of a user limiting the pruning operation to 1 or more courses / active versions
    if structure_filter is None:
        resultset = db.modulestore.structures.find({}, fields)
    else:
        resultset = db.modulestore.structures.find(structure_filter, fields)

    for structure_doc in resultset:
        
        """ 
        Get a list of all structures (or those relevant to the active versions via specified filter)
        This will give the list of Dictionary's with _id and previous_version 
        """
        
        structures_list.append(structure_doc)

    return structures_list

def prune_structures(db, structures_to_remove):

    """
    Prune the specified documents from the structures collection
    """

    # TODO: (performance): chunk up the removals to minimize possible production impact
    if len(structures_to_remove) == 0:
        return

    structures_removal_filter = { '$in' : [] }

    for structure_objectid_str in structures_to_remove:
        structures_removal_filter['$in'].append(ObjectId(structure_objectid_str))

    return db.modulestore.structures.remove ({'_id': structures_removal_filter})

# TODO: get this operational
def relink(db, available_version_list_with_prev_original, list_of_avail_id):

    """
    for each in available_version_list_with_prev_original:
        if each["previous_version"] is None:
            #print "Hi None"
            pass
        elif each["previous_version"] not in list_of_avail_id and each["previous_version"] is not None:
            to_be_linked_version_id = []
            # b = []
            original_version_id = []
            to_be_linked_version_id.append(each['_id'])
            # b.append(each['previous_version'])
            original_version_id.append(each['original_version'])
            print to_be_linked_version_id
            print original_version_id
            # we are appending into the array and linking it, Since $in in mongo query is expecting list
            db.modulestore.structures.update({'_id': {'$in': to_be_linked_version_id}},{'$set': {"previous_version": original_version_id[0]}})
        else:
            #print "Nothing to delete"
            pass
    """

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

def get_structures_to_delete(active_versions, structures=None, db=None, version_retention=2):

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
                            str(active_version['_id']))
                    )

                    # if the tree exceeds the minimum number of elements, 
                    # identify tree elements that should be removed
                    if tree_length > version_retention:

                        # track the required version: first & last
                        versions_to_retain.extend(version_tree[0])
                        versions_to_retain.append(version_tree[-1])
                    
                        # This will extract the mid range of 1 to n+1 version id's from the version_tree
                        versions_to_remove.extend(version_tree[1 : len(version_tree) -1 ]) 
                    
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
    return  { 'versions_to_remove':  versions_to_remove, 'version_trees': version_trees}

def get_database(connection, database_name="edxapp"):

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