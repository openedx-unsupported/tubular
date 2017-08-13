"""
A collection of functions related to pruning the openedx mongo structures
"""

import json
import os

from bson.objectid import ObjectId
from pymongo import MongoClient


class ModuleStore(object):
    """
    Handles pruning operations for the edx module store structues
    """

    # the dictionary keys to track for active versions
    target_active_versions_keys = [u'library', u'draft-branch', u'published-branch']

    def __init__(self, logger=None):

        # get reference to the user-specified python logger that has alreadt been initialized
        self.logger = logger
        self.db = None

    def initialize_database_connection(self, mongo_database_connection=None, mongo_database_name="edxapp"):

        """
        Initialize database connection
        """

        if mongo_database_connection is None:
            client = MongoClient()
        else:
            client = MongoClient(mongo_database_connection)

        self.db = client[mongo_database_name]

    def log(self, message, message_type="info"):

        """
        Log a message
        """

        if self.logger is not None:
            if message_type == "info":
                self.logger.info(message)
            else:
                self.logger.debug(message)

    def save_data_file(self, data, output_file):

        """
        Save the specified data file to disk
        """

        self.log("Saving the purged dataset to {0}".format(output_file))

        # write the updated dataset
        with open(output_file, 'w') as outfile:
            json.dump(data, outfile)

    def prune_structures_static_data(self, original_dataset, structures_to_remove):

        """
        Prune the static test data and return the results
        """

        pruned_static_data = []

        for structure_doc in original_dataset[u'structures']:

            if structure_doc[u'_id'] not in structures_to_remove:
                pruned_static_data.append(structure_doc)

        original_dataset[u'structures'] = pruned_static_data

        return original_dataset

    def load_test_dataset(self, dataset_file):

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

    def get_query_filter(self, doc_filter):

        """
        Generate a document filter for bulk querying
        """

        # establish the query filter  (respecting cases where no value is specified)
        query_filter = None

        if len(doc_filter['$in']) > 0:
            query_filter = {"_id": doc_filter}

        return query_filter

    def get_active_version_filter(self, active_version_id_list):

        """
        Generate document filter for bulk querying the active version collection
        """

        av_filter = {'$in': []}

        for active_version_id in active_version_id_list.split(","):
            av_filter['$in'].append(ObjectId(active_version_id.strip()))

        # establish the query filter  (respecting cases where no value is specified)
        return self.get_query_filter(av_filter)

    def get_structures_filter(self, active_version_list):

        """
        Generate document filter for bulk querying the structures collection
        """

        structure_filter = {'$in': []}

        for active_version in active_version_list:

            for target_key in self.target_active_versions_keys:
                if target_key in active_version['versions']:
                    structure_filter['$in'].append(ObjectId(active_version['versions'][target_key]))

        # establish the query filter  (respecting cases where no value is specified)
        return self.get_query_filter(structure_filter)

    def get_active_versions(self, active_version_list=None):

        """
        Get all documents from the active_versions collection
        """

        # establish the active version filter (if required)
        active_version_filter = None

        if active_version_list is not None:
            active_version_filter = self.get_active_version_filter(active_version_list)

        fields = {
            "versions.draft-branch": 1,
            "versions.published-branch": 1,
            "versions.library": 1,
        }

        # initialize our active versions dictionary
        active_versions = []

        # TODO: apply filters here in support of a user limiting the pruning operation to 1+ course/active versions
        if active_version_filter is None:
            resultset = self.db.modulestore.active_versions.find({}, fields)
        else:
            resultset = self.db.modulestore.active_versions.find(active_version_filter, fields)

        for active_version_doc in resultset:

            # collect all interesting docs: library & [draft|published]-branch active versions
            avdocs_versions = active_version_doc['versions']

            if u'library' in avdocs_versions \
                    or u'draft-branch' in avdocs_versions \
                    or u'published-branch' in avdocs_versions:
                active_versions.append(active_version_doc)

        # return the active versions
        return active_versions

    def get_structures(self, filter_enabled, active_versions_list):

        """
        Get all documents from the structures collection
        """

        # use filters (if required)
        structure_filter = None
        if filter_enabled:
            structure_filter = self.get_structures_filter(active_versions_list)

        fields = {
            "_id": 1,
            "previous_version": 1,
            "original_version": 1
        }

        structures_list = []

        # TODO: apply filters to support limiting the pruning operation to 1 or more courses / active versions
        if structure_filter is None:
            resultset = self.db.modulestore.structures.find({}, fields)
        else:
            resultset = self.db.modulestore.structures.find(structure_filter, fields)

        for structure_doc in resultset:
            # Get a list of all structures (or those relevant to the active versions via specified filter)
            # this will give the list of Dictionary's with _id and previous_version
            structures_list.append(structure_doc)

        return structures_list

    def prune_structures(self, structures_to_remove):

        """
        Prune the specified documents from the structures collection
        """

        # TODO: (performance): chunk up the removals to minimize possible production impact
        if len(structures_to_remove) == 0:
            return

        structures_removal_filter = {'$in': []}

        for structure_objectid_str in structures_to_remove:
            structures_removal_filter['$in'].append(ObjectId(structure_objectid_str))

        return self.db.modulestore.structures.remove({'_id': structures_removal_filter})

    def relink(self, structures):

        """
        Relink structures to their original version post pruning
        """

        self.log("Relinking structures to their original versions")

        index_position = 0
        available_ids = []

        # build a list of all available ids
        available_ids.extend([structure_doc['_id'] for structure_doc in structures])

        # iterate structures and relink to original
        for structure_doc in structures:

            if structure_doc["previous_version"] is not None and structure_doc["previous_version"] not in available_ids:

                self.log("{0} was not found in {1}".format(structure_doc["previous_version"], available_ids), "debug")

                to_be_linked_version_id = []
                original_version_id = []

                to_be_linked_version_id.append(structure_doc['_id'])
                original_version_id.append(structure_doc['original_version'])

                self.log("{0} version is being linked to {1}".format(to_be_linked_version_id, original_version_id[0]),
                         "debug")

                # TODO: refactor to support bulk updates for performance concerns
                if self.db is not None:

                    # this is a live update session
                    self.db.modulestore.structures.update(
                        {'_id': {'$in': to_be_linked_version_id}},
                        {'$set': {"previous_version": original_version_id[0]}})

                else:

                    # this is working against static dataset
                    structures[index_position][u'previous_version'] = original_version_id[0]

            else:
                self.log("Nothing to link for structure: {0}".format(structure_doc['_id']), "debug")

            # advance the index position
            index_position += 1

        return structures

    def find_previous_version(self, lookup_key, lookup_value, structures_list):

        """
        This function searches all structure documents for the one specified
        """

        # it is more efficient to use a structures list
        # instead of separate db calls (which may be necessary for supporting
        # pruning individual active versions)
        for structure_doc in structures_list:

            if structure_doc[lookup_key] == lookup_value:
                return structure_doc

    def build_activeversion_tree(self, active_version, structures):

        """
        Build a tree representing the active_version and its tree of ancestors
        from structures
        """

        # link the active version to its base version in structures
        structure_doc = self.find_previous_version('_id', active_version, structures)

        # map the tree for the identified structure
        version_tree = []

        # recursively identify the ancestors
        if structure_doc is not None:

            # build the tree
            version_tree.append(str(structure_doc['_id']))

            while structure_doc[u'previous_version'] is not None:

                # search for the parent structure doc
                structure_doc = self.find_previous_version('_id', structure_doc[u'previous_version'], structures)

                # build the tree - recursively
                if structure_doc is None:
                    # end of the tree (original version)
                    break

                version_tree.append(str(structure_doc['_id']))

        return version_tree

    def get_structures_to_delete(self, active_versions, structures=None, version_retention=2, relink_structures=False):

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

            for target_key in self.target_active_versions_keys:

                if target_key in active_version['versions']:

                    # print(active_version)
                    version_tree = self.build_activeversion_tree(active_version['versions'][target_key], structures)

                    # only add the tree if it has 1+ element
                    tree_length = len(version_tree)
                    if tree_length > 0:

                        status_message = "Processing Active Version {0} | {3}: {1} version with a {2}-version tree"

                        self.log(status_message.format(
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

    def get_database(self, connection, database_name):

        """
        Establish a connection to the database
        """

        if connection is None:
            client = MongoClient()
        else:
            client = MongoClient(connection)

        return client[database_name]
