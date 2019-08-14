""" Commands to interact with the GoCD API. """
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function, unicode_literals

import logging
from collections import namedtuple
from datetime import datetime, timedelta
from dateutil import tz

from yagocd import Yagocd as yagocd
from tubular.github_api import default_expected_release_date

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)


class AdvancementPipelineNotFound(Exception):
    """
    Raise when not finding an appropriate advancement pipeline.
    """
    pass


class AdvancementPipelineAlreadyAdvanced(Exception):
    """
    Raise when appropriate advancement pipeline has already been advanced.
    """
    pass


PipelineInstance = namedtuple('PipelineInstance', ['name', 'counter', 'url'])


class GoCDAPI(object):
    """
    Interacts with the GoCD API to perform common tasks.
    """
    def __init__(self, username, password, go_server_url):
        self.client = yagocd(
            server=go_server_url,
            auth=(username, password),
        )

    def approve_stage(self, pipeline_name, pipeline_counter, stage_name):
        """
        Approves the specified stage of the specified pipeline run.
        """
        LOG.info("Starting stage %s of pipeline %s:%s", stage_name, pipeline_name, pipeline_counter)
        self.client.stages.run(pipeline_name, pipeline_counter, stage_name)

    def fetch_pipeline_to_advance(self,
                                  advance_pipeline_name,
                                  advance_stage_name,
                                  check_ci_stage_name=None,
                                  relative_to=None):
        """
        Given:
            - the name of a pipeline to manually advance (the advancement pipeline)
            - a datetime representing the current time (typically the production release time)
        find the advancement pipeline that should be advanced/deployed to production.

        The algorithm:
        - Query the value stream map containing the upstream pipeline materials of the advancement pipeline.
        - Find the initial upstream pipeline material.
        - Check the time at which the first job of the first stage was triggered.
        - If the job was triggered before the last release time relative to the passed-in time, found.
        - If not, keep going backwards into pipeline history until found.

        Params:
            advance_pipeline_name (str): Pipeline name which contains the manual stage to advance.
            advance_stage_name (str): Stage name in pipeline which requires manual advancement.
            relative_to (datetime): Datetime relative to which the release should occur.
                If None, use the current datetime.

        Returns:
            PipelineInstance: Named tuple containing pipeline instance to advance.
        """
        def has_advanced(pipeline_instance, stage_name):
            """
            Check to see if a pipeline from a value stream map has been advanced.
            """
            return pipeline_instance.stage(stage_name).data['scheduled']

        def stage_failed(pipeline_instance, stage_name):
            """
            Check to see if a stage failed, if the stage name is not None
            """
            return stage_name is not None and pipeline_instance.stage(stage_name).data.get('result') != 'Passed'

        # Compute the previous release cutoff (in UTC) relative to the passed-in time -or- now.
        utc_zone = tz.gettz('UTC')
        relative_time = relative_to if relative_to else datetime.now(utc_zone)
        previous_release_cutoff = default_expected_release_date(relative_time - timedelta(days=1))

        LOG.info(
            'Checking for advancement pipeline "%s" relative to time %s, mapping to last release time %s.',
            advance_pipeline_name, relative_time, previous_release_cutoff
        )

        # Go backwards in advancement pipeline history, starting with the most recent run.
        for advancement_pipeline in self.client.pipelines.full_history(advance_pipeline_name):
            # Get the full instance information for the initial pipeline determined by the value stream map.
            vsm = advancement_pipeline.value_stream_map()
            initial_pipeline_inst = self.client.pipelines.get(vsm[0].data.name, vsm[0].data.counter)

            # Find the trigger timestamp from the first job in the first stage of the first pipeline.
            # Trigger timestamp is in milliseconds since the epoch time - convert to seconds.
            trigger_time = initial_pipeline_inst.stages()[0].jobs()[0].data.get('scheduled_date') / 1000

            # Convert the trigger timestamp to a UTC datetime.
            utc_trigger_time = datetime.utcfromtimestamp(trigger_time).replace(tzinfo=utc_zone)

            # Was the initial pipeline in the value stream map was triggered before the last release time?
            if utc_trigger_time < previous_release_cutoff:
                # Found the most recent pipeline to be triggered before the last release time.

                # Log relevant information.
                est_time = utc_trigger_time.astimezone(tz.gettz('America/New_York'))
                LOG.info('Found pipeline to advance: %s', advancement_pipeline.url)
                LOG.info('From initial pipeline: %s', initial_pipeline_inst.url)
                LOG.info('Initial pipeline %s was triggered at %s', initial_pipeline_inst.data.name, est_time)

                if stage_failed(advancement_pipeline, check_ci_stage_name):
                    LOG.info('Stage %s failed on %s, skipping to next older build',
                             check_ci_stage_name,
                             advancement_pipeline.url)
                    continue

                # Check to see if the pipeline has already been advanced.
                if has_advanced(advancement_pipeline, advance_stage_name):
                    LOG.info('But pipeline has already been advanced!')
                    raise AdvancementPipelineAlreadyAdvanced(
                        'Advancement pipeline "{}" found - but its stage "{}" has already been advanced.'.format(
                            advance_pipeline_name,
                            advance_stage_name
                        )
                    )

                # Return the advancement pipeline instance.
                return PipelineInstance(
                    advancement_pipeline.data.name,
                    advancement_pipeline.data.counter,
                    advancement_pipeline.url
                )

            elif has_advanced(advancement_pipeline, advance_stage_name):
                # This pipeline has already been advanced. Since we'd expect not to advance a pipeline
                # earlier than the last one advanced, stop at this point.
                raise AdvancementPipelineNotFound(
                    'More recent advanced pipeline was found - stopping historical search.'
                )

        raise AdvancementPipelineNotFound(
            'Could not find advancement pipeline for "{}" relative to time {},'
            ' which maps to last release time {}.'.format(
                advance_pipeline_name, relative_time, previous_release_cutoff
            )
        )
