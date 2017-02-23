"""
Tests for tubular.gocd_api.GoCDAPI
"""
from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime
from dateutil import tz
from easydict import EasyDict

from unittest import TestCase  # pylint: disable=wrong-import-order
import ddt
from mock import patch, Mock
from freezegun import freeze_time

from yagocd.session import Session
from yagocd.resources.pipeline import PipelineInstance
from tubular.gocd_api import GoCDAPI, AdvancementPipelineNotFound


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
            # Pipeline history entry, retrieved via pipelines.full_history().
            {
                'name': 'manual_verification_edxapp_prod_early_ami_build',
                'counter': fillin_params['manual_counter']
            },
            # Value stream map of the above history entry, retrieved with PipelineInstance.value_stream_map().
            (
                {
                    'name': u'prerelease_edxapp_materials_latest',
                    'counter': fillin_params['prerelease_counter']
                },
                {
                    'name': u'manual_verification_edxapp_prod_early_ami_build',
                    'counter': fillin_params['manual_counter']
                }
            ),
            # Pipeline instance data, retrieved via pipelines.get() method.
            (
                {
                    'name': 'prerelease_edxapp_materials_latest',
                    'counter': fillin_params['prerelease_counter'],
                    'stages': [
                        {
                            'name': 'initial_verification',
                            'jobs': [
                                {'name': 'armed_job', 'scheduled_date': fillin_params['job1_trigger_time']}
                            ]
                        },
                        {
                            'name': 'manual_verification',
                            'jobs': [],
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
                        },
                        {
                            'jobs': [],
                            'name': 'manual_verification'
                        }
                    ],
                }
            )
        )

    def _build_mocked_gocd_data(self, fillin_params):
        """
        Setup the GoCD data mocking for a single test.
        """
        instances = []
        for fillins in fillin_params:
            inst_data, vsm, gets = self._build_pipeline_system_data(fillins)
            # Build a mocked PipelineInstance and add it to a full_history() list.
            attrs = {
                'value_stream_map.return_value': [
                    Mock(spec=PipelineInstance, data=EasyDict(instance)) for instance in vsm
                ]
            }
            instances.append(Mock(spec=PipelineInstance, data=EasyDict(inst_data), **attrs))
            # Add the PipelineInstance data to the mocked get() call.
            self._build_gets(gets)
        return instances

    @ddt.data(
        (VALID_JOB_TRIGGER_TIME_MS, False),
        (INVALID_JOB_TRIGGER_TIME_MS, True)
    )
    @ddt.unpack
    def test_pipeline_instance_finding_using_specific_time(self, manual_trigger_time, exception_expected):
        """
        Verify that the correct pipeline instance is found, given the *current* time.
        """
        current_time = datetime(2017, 2, 18, 1, 0, 0, tzinfo=tz.gettz('UTC'))
        gocd_api_data = [
            {
                'prerelease_counter': 238,
                'manual_counter': 157,
                'job1_trigger_time': 1487707461420,
                'job2_trigger_time': 1487707461420 + FAKE_TIME_BETWEEN_PIPELINE_RUNS_MS
            },
            {
                'prerelease_counter': 228,
                'manual_counter': 148,
                'job1_trigger_time': manual_trigger_time,
                'job2_trigger_time': manual_trigger_time + FAKE_TIME_BETWEEN_PIPELINE_RUNS_MS
            }
        ]
        instances = self._build_mocked_gocd_data(gocd_api_data)

        with patch.object(self.test_gocd_client.client.pipelines, 'full_history', return_value=instances):
            with patch.object(self.test_gocd_client.client.pipelines, 'get', new=self._mock_gets):
                if exception_expected:
                    with self.assertRaises(AdvancementPipelineNotFound):
                        found_pipeline = self.test_gocd_client.fetch_pipeline_to_advance(
                            'manual_verification_edxapp_prod_early_ami_build',
                            current_time
                        )
                else:
                    found_pipeline = self.test_gocd_client.fetch_pipeline_to_advance(
                        'manual_verification_edxapp_prod_early_ami_build',
                        current_time
                    )
                    self.assertEqual(found_pipeline.data.name, 'manual_verification_edxapp_prod_early_ami_build')
                    self.assertEqual(found_pipeline.data.counter, 148)

    @freeze_time("2017-02-18 01:00:00")
    @ddt.data(
        (VALID_JOB_TRIGGER_TIME_MS, False),
        (INVALID_JOB_TRIGGER_TIME_MS, True)
    )
    @ddt.unpack
    def test_pipeline_instance_finding_using_now(self, manual_trigger_time, exception_expected):
        """
        Verify that the correct pipeline instance is found, given the *current* time.
        """
        gocd_api_data = [
            {
                'prerelease_counter': 238,
                'manual_counter': 157,
                'job1_trigger_time': 1487707461420,
                'job2_trigger_time': 1487707461420 + FAKE_TIME_BETWEEN_PIPELINE_RUNS_MS
            },
            {
                'prerelease_counter': 228,
                'manual_counter': 148,
                'job1_trigger_time': manual_trigger_time,
                'job2_trigger_time': manual_trigger_time + FAKE_TIME_BETWEEN_PIPELINE_RUNS_MS
            }
        ]
        instances = self._build_mocked_gocd_data(gocd_api_data)

        with patch.object(self.test_gocd_client.client.pipelines, 'full_history', return_value=instances):
            with patch.object(self.test_gocd_client.client.pipelines, 'get', new=self._mock_gets):
                if exception_expected:
                    with self.assertRaises(AdvancementPipelineNotFound):
                        found_pipeline = self.test_gocd_client.fetch_pipeline_to_advance(
                            'manual_verification_edxapp_prod_early_ami_build',
                        )
                else:
                    found_pipeline = self.test_gocd_client.fetch_pipeline_to_advance(
                        'manual_verification_edxapp_prod_early_ami_build'
                    )
                    self.assertEqual(found_pipeline.data.name, 'manual_verification_edxapp_prod_early_ami_build')
                    self.assertEqual(found_pipeline.data.counter, 148)

    def tearDown(self):
        self._instance_map = {}
        super(GoCDApiTestCase, self).tearDown()
