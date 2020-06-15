"""
Tests of the code which retrys calls.
"""

import datetime
import os
import unittest

import mock
from ddt import ddt, data, unpack
from six.moves import reload_module

from tubular.utils import retry

os.environ['TUBULAR_RETRY_ENABLED'] = "true"
reload_module(retry)  # pylint: disable=too-many-function-args


class UniqueTestException(Exception):
    """
    Mock exception to use in tests below.
    """


@ddt
class TestLifecycleManager(unittest.TestCase):
    """
    Tests for the retry decorator Lifecycle Manager
    """

    def test_max_attempts_less_than_1(self):
        self.assertRaises(retry.RetryException, retry.LifecycleManager, 0, 1, 1)

    def test_delay_seconds_less_than_0(self):
        self.assertRaises(retry.RetryException, retry.LifecycleManager, 1, -1, 1)

    def test_max_attempts_reached(self):
        manager = retry.LifecycleManager(1, 1, 1)
        # first call current_attempt_number should be 0 and max_attempts_reached should return False
        self.assertFalse(manager.max_attempts_reached())

        manager._current_attempt_number += 1
        self.assertFalse(manager.max_attempts_reached())

        # incrementing again should put us past the max attempts threshold
        manager._current_attempt_number += 1
        self.assertTrue(manager.max_attempts_reached())

    def test_max_time_reached_none(self):
        """
        When no max time is set, max_time_reached should always return False
        """
        manager = retry.LifecycleManager(1, 1, None)
        self.assertFalse(manager.max_time_reached())

    def test_max_time_reached(self):
        # Python built-in types are immutable so we can't use @mock.patch
        curr_time = datetime.datetime.utcnow()

        class NewDateTime(datetime.datetime):
            """
            Class to mock datetime.
            """

            @classmethod
            def utcnow(cls):
                """
                Method to always return specific UTC datetime.
                """
                return curr_time

        built_in_datetime = retry.datetime

        # The instance of datetime becomes local to the module it's import in to. We must patch datetime using the
        # module instance that is imported in to the ec2 module.
        retry.datetime = NewDateTime

        manager = retry.LifecycleManager(1, 1, 300)
        self.assertEqual(manager._max_datetime,
                         curr_time + datetime.timedelta(0, 300))  # pylint: disable=protected-access
        self.assertFalse(manager.max_time_reached())

        # set the expiration in the past and ensure that max_time_reached returns True
        manager = retry.LifecycleManager(1, 1, -1)
        self.assertEqual(manager._max_datetime,
                         curr_time + datetime.timedelta(0, -1))  # pylint: disable=protected-access
        self.assertTrue(manager.max_time_reached())

        # restore the default functionality of retry.datetime
        retry.datetime = built_in_datetime

    @data((True, True, True),
          (True, False, True),
          (False, True, True),
          (False, False, False))
    @unpack
    def test_done(self, max_time_ret_val, max_attempts_ret_val, expected_return_value):
        manager = retry.LifecycleManager(1, 1, 1)
        with mock.patch('tubular.utils.retry.LifecycleManager.max_attempts_reached', lambda x: max_attempts_ret_val):
            with mock.patch('tubular.utils.retry.LifecycleManager.max_time_reached', lambda x: max_time_ret_val):
                self.assertEqual(manager.done(), expected_return_value)

    def test_get_delay_time(self):
        manager = retry.LifecycleManager(1, 1, 1)
        self.assertEqual(manager.get_delay_time(), 1)

    def test_execute_success(self):
        string1 = 'argument 1'
        string2 = 'argument 2'

        def success_fn(arg1, arg2):
            """
            Function to mock success.
            """
            self.assertEqual(string1, arg1)
            self.assertEqual(string2, arg2)

        manager = retry.LifecycleManager(1, 1, None)
        with mock.patch(retry.__name__ + '.LifecycleManager.get_delay_time', lambda x: 0):
            manager.execute(success_fn, string1, string2)

    def test_execute_failure(self):
        manager = retry.LifecycleManager(1, 1, None)
        mock_func = mock.MagicMock()
        mock_func.side_effect = UniqueTestException
        mock_func.__name__ = 'TheMockTestFunction'
        with mock.patch(retry.__name__ + '.LifecycleManager.get_delay_time', lambda x: 0):
            self.assertRaises(UniqueTestException, manager.execute, mock_func, 'arg1', 'arg2')

    def test_execute_time_limit_exceeded(self):
        mock_func = mock.MagicMock()
        mock_func.side_effect = UniqueTestException
        mock_func.__name__ = 'TheMockTestFunction'
        # patch out the sleep time and ensure that max_attempts_reached always returns False
        # this ensures we are only testing that the end time has been reached for the exit condition
        with mock.patch(retry.__name__ + '.LifecycleManager.get_delay_time', lambda x: 0):
            with mock.patch(retry.__name__ + '.LifecycleManager.max_attempts_reached', lambda x: False):
                manager = retry.LifecycleManager(10000, 1, 1)
                self.assertRaises(UniqueTestException, manager.execute, mock_func, 'arg1', 'arg2')

    def test_execute_max_attempts_exceeded(self):
        mock_func = mock.MagicMock()
        mock_func.side_effect = UniqueTestException
        mock_func.__name__ = 'TheMockTestFunction'
        # patch out the sleep time and ensure that max_time_reached always returns False
        # this ensures we are only testing that the maximum number attempts have bee exceeded
        with mock.patch(retry.__name__ + '.LifecycleManager.get_delay_time', lambda x: 0):
            with mock.patch(retry.__name__ + '.LifecycleManager.max_time_reached', lambda x: False):
                manager = retry.LifecycleManager(2, 1, 500)
                self.assertRaises(UniqueTestException, manager.execute, mock_func, 'arg1', 'arg2')

    def test_execute_subsequent_attempts_succeed(self):
        """
        Test that the first call to execute fails, the second calls succeeds
        """
        mock_func = mock.MagicMock()
        mock_func.side_effect = [UniqueTestException, "success"]
        mock_func.__name__ = 'TheMockTestFunction'
        with mock.patch(retry.__name__ + '.LifecycleManager.get_delay_time', lambda x: 0):
            manager = retry.LifecycleManager(2, 1, 500)
            self.assertEqual("success", manager.execute(mock_func, 'arg1', 'arg2'))
