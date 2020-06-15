"""
A collection of functions related to pruning the openedx mongo structures
"""

import json
import os

from bson.objectid import ObjectId
from pymongo import MongoClient


class ModuleStore:
    """
    Handles pruning operations for the edx module store structures

    Here are schemas for key objects referenced in this class:

    active_version: dictionary representing an active_version document
        ** '_id': an ObjectId (guid)
        ** 'versions': dictionary of versions
            ** 'draft-branch': draft branch version
            ** 'published-branch': published branch version
            ** 'library': library version

    structure: dictionary representing a structure document:
        ** '_id': an ObjectId (guid)
        ** 'original_version': the original structure id in the previous_version relation
        ** 'previous_version': the structure id from which this one was derived. For published courses, this
                                points to the previously published version of the structure not the draft
                                published to this.

    """

    # the dictionary keys to track for active versions
    target_active_versions_keys = ['library', 'draft-branch', 'published-branch']

    def __init__(self, logger=None):

        # get reference to the user-specified python logger that has alreadt been initialized
        self.logger = logger
        self.db = None

        # retention minimum
        self._minimum_version_retention = 3

    def initialize_database_connection(self, mongo_database_connection=None, mongo_database_name="edxapp"):

        """
        Initialize database connection

        :param mongo_database_connection: connection string to mongo database. If none is specified, localhost is used.
        :param mongo_database_name: name of the mongo database the application will interact with

        """

        if not mongo_database_connection:
            client = MongoClient()
        else:
            client = MongoClient(mongo_database_connection)

        self.db = client[mongo_database_name]

    def log(self, message, message_type="info"):

        """
        Log a message

        :param message: the message to log
        :param message_type: the type of log message (info, warning or debug). If a message is not info or warning, it
        falls back to debug

        """

        if self.logger:
            if message_type == "info":
                self.logger.info(message)

            elif message_type == "warning":
                self.logger.warning(message)

            else:
                self.logger.debug(message)

    def save_data_file(self, data, output_file=None, output_file_object=None):

        """
        Save the specified data file to disk

        :param data: the active versions and/or structure data being saved
        :param output_file: path to an output file to save the data
        :param output_file_object: tempfile file-like object for saving temporary files

        This function supports two options:
        1. specifying the output file name - output will be saved at the path specified
        2. a file-like object returned from tempfile.NamedTemporaryFile

        Either output_file or output_file_object must be specified. If both are specified,
        output_file will be preferred. If none is specified, an exception will be raised.

        """

        if output_file:
            self.log("Saving the purged dataset to %s" % output_file)

            # write the updated dataset
            with open(output_file, 'w') as outfile:
                json.dump(data, outfile)

        elif output_file_object:
            self.log("Saving the purged dataset using tempfile file-like object")
            output_file_object.write(json.dumps(data).encode())

        else:
            raise ValueError("you must specify either the output_file or output_file_object")

    def prune_structures_static_data(self, structures, structures_to_remove):

        """
        Prune the static test data and return the results

        :param structures: list of structure dictionaries (see dictionary definition in class docstring)
        :param structures_to_remove: list of ObjectIds representing Ids of structures that should be pruned
        :return: list of structure dictionaries

        """

        return [structure_doc for structure_doc in structures if structure_doc['_id'] not in structures_to_remove]

    def load_test_dataset(self, dataset_file):

        """
        Load the json data set from the file specified

        :param dataset_file: file containing the test data set
            ** 'active_versions': list of active version dictionaries
            ** 'structures': list of structure dictionaries
        :return: dictionary representing the test data set

        """

        # check if the specified file exists
        file_exists = os.path.isfile(dataset_file)

        if not file_exists:
            raise IOError("The specified file doesn't exist:"
                          " {dataset_file}".format(dataset_file=dataset_file))

        # load the file
        with open(dataset_file) as dataset:
            data = json.load(dataset)

        return data

    def get_query_filter(self, doc_filter):

        """
        Generate a document filter for bulk querying

        :param doc_filter: dictionary representing a mongo bulk query filter
            ** '$in': list of document ids guids
        :return: fully formed mongo query filter

        """

        # establish the query filter  (respecting cases where no value is specified)
        query_filter = {}

        if doc_filter['$in']:
            query_filter = {"_id": doc_filter}

        return query_filter

    def get_active_version_filter(self, active_version_id_list):

        """
        Generate document filter for bulk querying the active version collection

        :param active_version_id_list: list of ids for active versions
        :return: fully formed mongo query filter

        """

        filter_list = [ObjectId(active_version_id.strip()) for active_version_id in active_version_id_list.split(",")]
        av_filter = {'$in': filter_list}

        # establish the query filter (respecting cases where no value is specified)
        return self.get_query_filter(av_filter)

    def get_structures_filter(self, active_version_list=None):

        """
        Generate document filter for bulk querying the structures collection

        :param active_version_list: list of active version dictionaries (see dictionary definition in class docstring)
        :return: fully formed mongo query filter

        """

        structure_filter = {'$in': []}

        for active_version in active_version_list:

            # check for unknown versions
            unknown_versions = [
                version for version in active_version['versions']
                if version not in self.target_active_versions_keys
            ]

            if unknown_versions:
                message = "%s are not currently tracked for pruning" % unknown_versions
                self.log(message, "warning")

            for target_key in self.target_active_versions_keys:
                if target_key in active_version['versions']:
                    structure_filter['$in'].append(ObjectId(active_version['versions'][target_key]))

        # establish the query filter  (respecting cases where no value is specified)
        return self.get_query_filter(structure_filter)

    def get_active_versions(self, active_version_list=None):

        """
        Get all documents from the active_versions collection
        :param active_version_list: list of active version dictionaries (see dictionary definition in class docstring)
        :return: list of active version dictionaries

        """

        # establish the active version filter (if required)
        active_version_filter = None

        if active_version_list:
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

            if 'library' in avdocs_versions \
                    or 'draft-branch' in avdocs_versions \
                    or 'published-branch' in avdocs_versions:
                active_versions.append(active_version_doc)

        # return the active versions
        return active_versions

    def get_structures(self, active_versions=None):

        """
        Get all documents from the structures collection

        :param active_versions: list of active version dictionaries (see dictionary definition in class docstring)
        :return: list of structure dictionaries (see dictionary definition in class docstring)
        """

        # use filters (if required)
        structure_filter = None
        if active_versions:
            # TODO: implement structure filtering based on specified active versions
            structure_filter = self.get_structures_filter()

        fields = {
            "_id": 1,
            "previous_version": 1,
            "original_version": 1
        }

        # Get a list of all structures (or those relevant to the active versions via specified filter)
        structure_docs = self.db.modulestore.structures.find(structure_filter, fields)

        return list(structure_docs)

    def prune_structures(self, structures_to_remove):

        """
        Prune the specified documents from the structures collection

        :param structures_to_remove: list of structure ids targeted for removal
        :return: mongo WriteResult object representing the status of the operation

        """

        # TODO: (performance): chunk up the removals to minimize possible production impact
        if not structures_to_remove == 0:
            return

        structures_removal_filter = {
            '$in': [ObjectId(oid) for oid in structures_to_remove]
        }

        return self.db.modulestore.structures.remove(structures_removal_filter)

    def relink(self, structures):

        """
        Relink structures to their original version post pruning

        :param structures: list of structure dictionaries to relink (see dictionary definition in class docstring)
        :return: list of structure dictionaries relinked to their original versions

        """

        self.log("Relinking structures to their original versions")

        # build a list of all available ids
        available_ids = {structure_doc['_id'] for structure_doc in structures}

        # iterate structures and relink to original
        for index_position, structure_doc in enumerate(structures):

            if structure_doc["previous_version"] and structure_doc["previous_version"] not in available_ids:

                message = "%s was not found in %s" % (structure_doc["previous_version"], available_ids)
                self.log(message, "debug")

                to_be_linked_version_id = []
                original_version_id = []

                to_be_linked_version_id.append(structure_doc['_id'])
                original_version_id.append(structure_doc['original_version'])

                message = "%s version is being linked to %s" % (to_be_linked_version_id, original_version_id[0])
                self.log(message, "debug")

                # TODO: refactor to support bulk updates for performance concerns
                if self.db:

                    # this is a live update session
                    self.db.modulestore.structures.update(
                        {'_id': {'$in': to_be_linked_version_id}},
                        {'$set': {"previous_version": original_version_id[0]}})

                else:

                    # this is working against static dataset
                    structures[index_position]['previous_version'] = original_version_id[0]

            else:
                self.log("Nothing to link for structure: %s" % structure_doc['_id'], "debug")

            # advance the index position
            index_position += 1

        return structures

    def find_previous_version(self, lookup_key, lookup_value, structures):

        """
        This function searches all structure documents for the one specified

        :param lookup_key: dictionary key to use for lookups
        :param lookup_value: expected value of the dictionary field to establish a match
        :param structures: list of structure dictionaries (see dictionary definition in class docstring)
        :return: structure dictionary with matching key/value or None

        """

        # TODO: Perf improvements needed here (ie: using lookup dictionary instead)
        # it is more efficient to use a structures list
        # instead of separate db calls (which may be necessary for supporting
        # pruning individual active versions)
        for structure_doc in structures:

            if structure_doc[lookup_key] == lookup_value:
                return structure_doc

    def build_active_version_ancestry(self, active_version, structures):

        """
        Build a tree representing the active_version and its list of ancestors from structures
        :param active_version: an active version dictionary (see dictionary definition in class docstring)
        :param structures: list of structure dictionaries (see dictionary definition in class docstring)
        :return: list of structures representing an active version lineage
        """

        # link the active version to its base version in structures
        structure_doc = self.find_previous_version('_id', active_version, structures)

        # map the ancestors for the identified structure
        version_ancestry = []

        # recursively identify the ancestors
        if structure_doc:

            # build the ancestral list
            version_ancestry.append(str(structure_doc['_id']))

            while structure_doc['previous_version']:

                # search for the parent structure doc
                structure_doc = self.find_previous_version('_id', structure_doc['previous_version'], structures)

                # build the ancestral list - recursively
                if not structure_doc:
                    # start of the lineage (original version)
                    break

                version_ancestry.append(str(structure_doc['_id']))

        return version_ancestry

    def get_structures_to_delete(self, active_versions, structures=None, version_retention=3):

        """
        Generate a list of structures that meet the conditions for pruning and associated visualization

        :param active_versions: list of active version dictionaries (see dictionary definition in class docstring)
        :param structures: list of structure dictionaries (see dictionary definition in class docstring)
        :param version_retention: number of structures to retain after purge excluding the original version
        :return: set of structures to be removed and their ancestry list
        """

        # initialize key variables
        version_ancestry_lists = []
        versions_to_retain = []
        versions_to_remove = []
        counter = 0

        # defensive: ensure that version_retention >=3
        if version_retention < self._minimum_version_retention:
            message_template = "Version retention of %s is below the minimum allowed and is being updated to %s"
            self.log(message_template % (version_retention, self._minimum_version_retention), "info")

        # iterate the active versions and build the associated version tree
        for counter, active_version in enumerate(active_versions, start=1):

            for target_key in self.target_active_versions_keys:

                if target_key in active_version['versions']:

                    # print(active_version)
                    version_ancestry_list = self.build_active_version_ancestry(
                        active_version['versions'][target_key],
                        structures)

                    # only add the tree if it has 1+ element
                    if version_ancestry_list:

                        status_message = "Processing Active Version %s | %s: %s version with a %s-version tree"

                        self.log(status_message % (
                            counter,
                            str(active_version['_id']),
                            target_key,
                            len(version_ancestry_list)))

                        # if the tree exceeds the minimum number of elements,
                        # identify tree elements that should be removed
                        if len(version_ancestry_list) > version_retention:
                            # track the required version: first & last
                            versions_to_retain.extend(version_ancestry_list[:2])
                            versions_to_retain.append(version_ancestry_list[-1])

                            # This will extract the mid range of 1 to n+1 version id's from the version_ancestry_list
                            versions_to_remove.extend(
                                version_ancestry_list[version_retention - 1: len(version_ancestry_list) - 1])

                            # tree mapping is complete, add to forest/list of trees
                        # only useful for dry runs and graphing purposes
                        version_ancestry_lists.append(version_ancestry_list)

        # All trees have been processed.
        # We now have a final list of structures to retain & remove

        # remove duplicates from the versions_to_retain
        versions_to_retain = list(set(versions_to_retain))

        # TODO: Performance improvements: evaluate if keeping as set is more optimal than as list
        # remove structures on the versions_to_remove list that are on the versions_to_retain list
        # this supports course re-runs and related links
        versions_to_remove = set(versions_to_remove) - set(versions_to_retain)

        # return the set of items to remove and the associated list of version trees
        return {'versions_to_remove': versions_to_remove, 'version_ancestry_lists': version_ancestry_lists}

    def get_database(self, connection, database_name):

        """
        Establish a connection to the database

        :param connection: connection string to mongo database
        :param database_name: name of the database
        :return: mongo database client reference
        """

        if connection is None:
            client = MongoClient()
        else:
            client = MongoClient(connection)

        return client[database_name]
