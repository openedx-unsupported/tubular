"""
Tests for tubular.gocd_api.GoCDAPI
"""

from datetime import datetime
from functools import partial
from unittest import TestCase  # pylint: disable=wrong-import-order

import ddt
from dateutil import tz
from freezegun import freeze_time
from mock import patch, Mock
from yagocd.resources.pipeline import PipelineInstance
from yagocd.session import Session

from tubular.gocd_api import (
    GoCDAPI, AdvancementPipelineNotFound, AdvancementPipelineAlreadyAdvanced
)


def convert_to_timestamp(dtime):
    """
    Given a datetime, return a POSIX timestamp (seconds since the epoch).
    """
    utc_naive = dtime.replace(tzinfo=None) - dtime.utcoffset()
    return (utc_naive - datetime(1970, 1, 1)).total_seconds()


VALID_JOB_TRIGGER_TIME_MS = convert_to_timestamp(datetime(2017, 2, 16, 15, 30, 00, tzinfo=tz.gettz('EST'))) * 1000
INVALID_JOB_TRIGGER_TIME_MS = convert_to_timestamp(datetime(2017, 2, 17, 10, 30, 00, tzinfo=tz.gettz('EST'))) * 1000
FAKE_TIME_BETWEEN_PIPELINE_RUNS_MS = 14000


@ddt.ddt
class GoCDApiTestCase(TestCase):
    """
    Tests the functionality of the GoCD API.
    All network calls are mocked out.
    """
    _instance_map = {}

    def setUp(self):
        """
        Setup a mocked GoCDAPI client for use in tests.
        """
        with patch('yagocd.session.Session', spec=Session):
            self.test_gocd_client = GoCDAPI('user', 'password', 'http://gocd')
        super(GoCDApiTestCase, self).setUp()

    def _build_gets(self, gets):
        """
        Build up the PipelineInstance objects to return.
        """
        with patch('yagocd.session.Session', spec=Session) as mock_session:
            for instance in gets:
                self._instance_map[(instance['name'], instance['counter'])] = PipelineInstance(mock_session, instance)

    def _mock_gets(self, name, counter):
        """
        Return a mocked PipelineInstance based on pipeline instance name & counter.
        """
        return self._instance_map[(name, counter)]

    def _build_pipeline_system_data(self, fillin_params):
        """
        Build the mocked JSON data that would be returned from the GoCD api.
        Many keys/values are left out - only the essential ones for testing remain.
        """
        return (
            {
                'name': 'prerelease_edxapp_materials_latest',
                'counter': fillin_params['prerelease_counter'],
                'stages': [
                    {
                        'name': 'initial_verification',
                        'jobs': [
                            {'name': 'armed_job', 'scheduled_date': fillin_params['job1_trigger_time']}
                        ],
                        'scheduled': fillin_params['stage_status']
                    },
                    {
                        'name': 'manual_verification',
                        'jobs': [],
                        'scheduled': fillin_params['stage_status']
                    }
                ],
            },
            {
                'name': 'manual_verification_edxapp_prod_early_ami_build',
                'counter': fillin_params['manual_counter'],
                'stages': [
                    {
                        'name': 'initial_verification',
                        'jobs': [
                            {'name': 'armed_job', 'scheduled_date': fillin_params['job2_trigger_time']}
                        ],
                        'scheduled': fillin_params['stage_status']
                    },
                    {
                        'name': 'manual_verification',
                        'jobs': [],
                        'scheduled': fillin_params['stage_status']
                    }
                ],
            }
        )

    def _build_mocked_gocd_data(self, fillin_params):
        """
        Setup the GoCD data mocking for a single test.
        """
        instances = []
        with patch('yagocd.session.Session', spec=Session) as mock_session:
            for fillins in fillin_params:
                inst_data = self._build_pipeline_system_data(fillins)

                # Build the value_stream_map() to return for the pipeline instance.
                vsm_data = [PipelineInstance(mock_session, instance) for instance in inst_data]

                # Build a mocked PipelineInstance for the manual_verification pipeline
                # and add it to a full_history() list.
                mock_instance = PipelineInstance(mock_session, inst_data[1])
                mock_instance.value_stream_map = Mock(return_value=vsm_data)
                instances.append(mock_instance)

                # Add the PipelineInstance data to the mocked get() call.
                self._build_gets(inst_data)
        return instances

    def _test_pipeline_instance_finding(
            self, manual_trigger_time, stage_statuses, exception_expected=None, current_time=None
    ):
        """
        Test pipeline instance finding using common code for the tests below.
        """
        gocd_api_data = [
            {
                'prerelease_counter': 238,
                'manual_counter': 157,
                'job1_trigger_time': 1487707461420,
                'job2_trigger_time': 1487707461420 + FAKE_TIME_BETWEEN_PIPELINE_RUNS_MS,
                'stage_status': stage_statuses[0]
            },
            {
                'prerelease_counter': 228,
                'manual_counter': 148,
                'job1_trigger_time': manual_trigger_time,
                'job2_trigger_time': manual_trigger_time + FAKE_TIME_BETWEEN_PIPELINE_RUNS_MS,
                'stage_status': stage_statuses[1]
            }
        ]
        instances = self._build_mocked_gocd_data(gocd_api_data)

        with patch.object(self.test_gocd_client.client.pipelines, 'full_history', return_value=instances):
            with patch.object(self.test_gocd_client.client.pipelines, 'get', new=self._mock_gets):
                fetch_func = partial(
                    self.test_gocd_client.fetch_pipeline_to_advance,
                    'manual_verification_edxapp_prod_early_ami_build',
                    'manual_verification',
                    None,
                )
                if exception_expected:
                    with self.assertRaises(exception_expected):
                        if current_time:
                            found_pipeline = fetch_func(current_time)
                        else:
                            found_pipeline = fetch_func()
                else:
                    if current_time:
                        found_pipeline = fetch_func(current_time)
                    else:
                        found_pipeline = fetch_func()
                    self.assertEqual(found_pipeline.name, 'manual_verification_edxapp_prod_early_ami_build')
                    self.assertEqual(found_pipeline.counter, 148)

    INSTANCE_FIND_TEST_DATA = (
        (VALID_JOB_TRIGGER_TIME_MS, (False, False), None),
        (VALID_JOB_TRIGGER_TIME_MS, (True, True), AdvancementPipelineNotFound),
        (VALID_JOB_TRIGGER_TIME_MS, (False, True), AdvancementPipelineAlreadyAdvanced),
        (INVALID_JOB_TRIGGER_TIME_MS, (False, False), AdvancementPipelineNotFound)
    )

    @ddt.data(*INSTANCE_FIND_TEST_DATA)
    @ddt.unpack
    def test_pipeline_instance_finding_using_specific_time(
            self, manual_trigger_time, stage_statuses, exception_expected
    ):
        """
        Verify that the correct pipeline instance is found, given the passed-in time.
        """
        self._test_pipeline_instance_finding(
            manual_trigger_time,
            stage_statuses,
            exception_expected,
            datetime(2017, 2, 18, 1, 0, 0, tzinfo=tz.gettz('UTC'))
        )

    @freeze_time("2017-02-18 01:00:00")
    @ddt.data(*INSTANCE_FIND_TEST_DATA)
    @ddt.unpack
    def test_pipeline_instance_finding_using_now(
            self, manual_trigger_time, stage_statuses, exception_expected
    ):
        """
        Verify that the correct pipeline instance is found, given the *current* time of now().
        """
        self._test_pipeline_instance_finding(
            manual_trigger_time,
            stage_statuses,
            exception_expected
        )

    def test_pipeline_instance_finding_with_no_data(self):
        """
        Verify proper behavior when no history data is returned.
        """
        instances = self._build_mocked_gocd_data([])
        with patch.object(self.test_gocd_client.client.pipelines, 'full_history', return_value=instances):
            with self.assertRaises(AdvancementPipelineNotFound):
                self.test_gocd_client.fetch_pipeline_to_advance(
                    'manual_verification_edxapp_prod_early_ami_build',
                    'manual_verification'
                )

    def tearDown(self):
        self._instance_map = {}
        super(GoCDApiTestCase, self).tearDown()
