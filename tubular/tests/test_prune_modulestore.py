"""
Tests for pruning modulestore
"""

from __future__ import absolute_import

import logging
import os
import sys
import unittest
import tubular.modulestore as modulestore


class TestModuleStorePruning(unittest.TestCase):

    """
    Test basic modulestore pruning
    """

    # output file for post-prune data
    output_file = os.path.join(os.path.dirname(__file__), "output.json")

    # input file: static dataset
    input_file = os.path.join(os.path.dirname(__file__), "test_prune_modulestore_data.json")

    # module store reference
    module_store = None

    # test data
    test_data = None

    def remove_output_file(self):

        """
        Removes residual test output
        """
        # check if the specified file exists
        file_exists = os.path.isfile(self.output_file)

        assert isinstance(file_exists, object)
        if file_exists:
            # there is residual output
            os.remove(self.output_file)

    @classmethod
    def setUpClass(cls):
        super(TestModuleStorePruning, cls).setUpClass()

        # intialize the logger
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        logger = logging.getLogger(__name__)

        # initialize the module store libraries
        cls.module_store = modulestore.ModuleStore(logger)

        # load the test data
        # testmode_data = data
        # we are using test data
        cls.test_data = cls.module_store.load_test_dataset(cls.input_file)

    def setUp(self):
        # make sure we remove any residual output file
        # this is defensive

        super(TestModuleStorePruning, self).setUp()
        self.remove_output_file()

    def find_structure(self, structures, key):
        """
        Support function for locating a structure from a list of structures
        """

        found = False
        for structure_doc in structures:
            if structure_doc['_id'] == key:
                found = True
                break

        return found

    def test_default_structures_prune(self):

        """
        Run the structure pruning operation
        """

        # quick test on the data
        active_versions = self.test_data[u'active_versions']
        structures = self.test_data[u'structures']

        # identify structures that should be deleted
        version_retention = 2
        relink_structures = True

        structure_prune_data = self.module_store.get_structures_to_delete(
            active_versions,
            structures,
            version_retention,
            relink_structures)

        # we are pruning the static data instead of the database
        pruned_dataset = self.module_store.prune_structures_static_data(
            self.test_data,
            structure_prune_data['versions_to_remove'])

        if relink_structures:
            pruned_dataset[u'structures'] = self.module_store.relink(pruned_dataset[u'structures'])

        # basic output test
        # there should be no changes to the active versions
        self.assertEqual(len(self.test_data[u'active_versions']), len(pruned_dataset[u'active_versions']))

        # save the output
        output_data_file = os.path.join(os.path.dirname(__file__), self.output_file)
        self.module_store.save_data_file(pruned_dataset, output_data_file)

        # test for output file
        self.assertEqual(True, os.path.isfile(output_data_file))

        # after pruning, the remaining structures will be 15
        self.assertEqual(9, len(pruned_dataset[u'structures']))

        # perform correctness tests: specific structures would have been pruned
        self.assertEqual(False, self.find_structure(pruned_dataset[u'structures'], '58dd0fd4620de9c0c9793627'))
        self.assertEqual(False, self.find_structure(pruned_dataset[u'structures'], '58dd0fd4620de9c0c9ea7e27'))
        self.assertEqual(False, self.find_structure(pruned_dataset[u'structures'], '58cd0fd4620dedc0c9ea7e29'))

if __name__ == '__main__':
    unittest.main()
