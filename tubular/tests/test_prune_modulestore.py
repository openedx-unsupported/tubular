"""
Tests for pruning modulestore
"""

import logging
import os
import sys
import tempfile
import unittest

import tubular.modulestore as modulestore


class TestModuleStorePruning(unittest.TestCase):
    """
    Test basic modulestore pruning

    This test class consumes a sample dataset and execute various tests
    against the dataset. The basic pattern for testing against a custom
    dataset is as follows:

    1.  create your custom dataset and save it (reference structure of
        test_prune_modulestore_data.json)
    2.  add the new datafile to the test folder
    3.  run the tests

    How to generate the custom dataset
    1. query the active_versions collection with the following
       selection fields and any custom filter to limit the dataset:

       fields = {
            "versions.draft-branch": 1,
            "versions.published-branch": 1,
            "versions.library": 1,
        }

        The results can be saved as a list of dictionaries. This
        forms the "active_versions" dictionary key in the sample dataset.

    2. query the structures collection with the following selection
       fields:

       fields = {
            "_id": 1,
            "previous_version": 1,
            "original_version": 1
        }

        Limiting the dataset is difficult and requires iterative queries
        that can be costly when run against a large production database.
        The results can be saved as a list of dictionaries. This forms the
        "structures" dictionary key in the sample dataset. Make sure to remove
        all dictionaries with duplicate _id values.

    """

    # input file: static data set
    input_file = os.path.join(os.path.dirname(__file__), "test_prune_modulestore_data.json")

    # module store reference
    module_store = None

    # test data
    test_data = None

    @classmethod
    def setUpClass(cls):
        super(TestModuleStorePruning, cls).setUpClass()

        # initialize the logger
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        LOG = logging.getLogger(__name__)

        # initialize the module store libraries
        cls.module_store = modulestore.ModuleStore(LOG)

    def setUp(self):
        super(TestModuleStorePruning, self).setUp()

        # load the test data
        self.module_store.log("Loading test data")
        self.test_data = self.module_store.load_test_dataset(self.input_file)

    def find_structure(self, structures, key):

        """
        Support function for locating a structure from a list of structures

        :param structures: list of structure dictionaries:
            ** '_id': an ObjectId (guid),
            ** 'original_version': the original structure id in the previous_version relation
            ** 'previous_version': the structure id from which this one was derived. For published courses, this
                                    points to the previously published version of the structure not the draft
                                    published to this.
        :param key: name of a dictionary key in structures to use for lookup

        """

        return any(structure_doc['_id'] == key for structure_doc in structures)

    def get_unique_structure_ids(self, structures):

        """
        Generate a unique set of structure ids from the provided list of structures

        :param structures: list of structure dictionaries:
            ** '_id': an ObjectId (guid),
            ** 'original_version': the original structure id in the previous_version relation
            ** 'previous_version': the structure id from which this one was derived. For published courses, this
                                    points to the previously published version of the structure not the draft
                                    published to this.

        """

        unique_structure_ids = {structure_doc['_id'] for structure_doc in structures}
        return unique_structure_ids

    def prune_structure(self,
                        version_retention=2,
                        removed_structure_ids=None,
                        retained_structure_ids=None,
                        output_file_path=None):

        """
        Run the structure pruning operation

        :param version_retention: the number of structures to retain in a course/library ancestral list post pruning
        :param removed_structure_ids: list of structure ids expected to be removed (used for correctness test)
        :param retained_structure_ids: list of structure ids expected to be retained (used for correctness test)
        :param output_file_path: file system path to save the pruned result set (used for visualization)

        """

        # quick test on the data
        active_versions = self.test_data['active_versions']
        structures = self.test_data['structures']

        self.module_store.log("Using Retention=%s" % version_retention)
        structure_prune_data = self.module_store.get_structures_to_delete(
            active_versions,
            structures,
            version_retention)

        # we are pruning the static data instead of the database
        pruned_structures = self.module_store.prune_structures_static_data(
            self.test_data['structures'],
            structure_prune_data['versions_to_remove'])

        relinked_pruned_structures = self.module_store.relink(pruned_structures)

        # basic output test

        # reassemble the dataset
        pruned_dataset = {'active_versions': active_versions, 'structures': relinked_pruned_structures}

        # save the output
        output_data_file_object = tempfile.NamedTemporaryFile(delete=True)

        try:

            # exercise the file save
            self.module_store.save_data_file(
                data=pruned_dataset,
                output_file_object=output_data_file_object)

            # optionally save the output if a path is specified
            if output_file_path:
                self.module_store.save_data_file(
                    data=pruned_dataset,
                    output_file=output_file_path)

            # dynamically determine the count of structure after pruning
            unique_structure_ids = self.get_unique_structure_ids(structures)
            expected_pruned_versions_count = len(unique_structure_ids) - len(structure_prune_data['versions_to_remove'])

            # validate the expected count of post-prune structures
            self.assertEqual(expected_pruned_versions_count, len(relinked_pruned_structures))

            # perform correctness tests: check structures that should be removed
            if removed_structure_ids:
                for structure_id in removed_structure_ids:
                    self.module_store.log("Check: %s should be removed" % structure_id)
                    self.assertEqual(False, self.find_structure(relinked_pruned_structures, structure_id))

            # perform correctness tests: check structures that should be retained
            if retained_structure_ids:
                for structure_id in retained_structure_ids:
                    self.module_store.log("Check: %s should be retained" % structure_id)
                    self.assertEqual(True, self.find_structure(relinked_pruned_structures, structure_id))

        finally:
            # ensure removal of the temp file
            output_data_file_object.close()

    def test_structures_prune(self):

        """
        Test structure pruning with retention = 3
        This means, the course/library ancestral tree will contain at most
        4 members: the active version, its previous version and the original version
        """

        # the below filters are specific to the test data
        # active, previous & original versions must be retained.
        # The third structure in ancestry will be retained (retention=3)
        retained_structures = ['595f47eae9ec2154eceba297', '58dd9d18620de9c0be7937c3', '583602b0e9ec21ec98727b80',
                               '58dd0fd4620de9c0c9793627']

        # fourth & fifth structures in ancestry must be removed (retention=2)
        removed_structures = ['58cd0fd4620dedc0c9ea7e29', '58dd0fd4620de9c0c9ea7e27']

        self.prune_structure(version_retention=4,
                             retained_structure_ids=retained_structures,
                             removed_structure_ids=removed_structures,
                             output_file_path="/tmp/output.json")

    def test_default_structures_prune(self):

        """
        Test structure pruning with retention = 2
        This means, the course/library ancestral tree will contain at most
        3 members: the active version, its previous version and the original version
        """

        # the below filters are specific to the test data
        # active, previous & original versions must be retained
        retained_structures = ['595f47eae9ec2154eceba297', '58dd9d18620de9c0be7937c3', '583602b0e9ec21ec98727b80']

        # third, fourth & fifth structures in ancestry must be removed (retention=2)
        removed_structures = ['58dd0fd4620de9c0c9793627', '58cd0fd4620dedc0c9ea7e29', '58dd0fd4620de9c0c9ea7e27']

        self.prune_structure(retained_structure_ids=retained_structures, removed_structure_ids=removed_structures)


if __name__ == '__main__':
    unittest.main()
