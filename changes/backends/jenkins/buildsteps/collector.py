from __future__ import absolute_import

from flask import current_app
from hashlib import md5

from changes.backends.jenkins.buildstep import JenkinsBuildStep
from changes.backends.jenkins.generic_builder import JenkinsGenericBuilder
from changes.config import db
from changes.constants import Status
from changes.db.utils import get_or_create
from changes.jobs.sync_job_step import sync_job_step
from changes.models import JobPhase, JobStep


class JenkinsCollectorBuildStep(JenkinsBuildStep):
    """
    Fires off a generic job with parameters:

        CHANGES_BID = UUID
        CHANGES_PID = project slug
        REPO_URL    = repository URL
        REPO_VCS    = hg/git
        REVISION    = sha/id of revision
        PATCH_URL   = patch to apply, if available
        SCRIPT      = command to run

    A "jobs.json" is expected to be collected as an artifact with the following
    values:

        {
            "phase": "Name of phase",
            "jobs": [
                {"name": "Optional name",
                 "cmd": "echo 1"},
                {"cmd": "py.test --junit=junit.xml"}
            ]
        }

    For each job listed, a new generic task will be executed grouped under the
    given phase name.
    """
    # TODO(dcramer): longer term we'd rather have this create a new phase which
    # actually executes a different BuildStep (e.g. of order + 1), but at the
    # time of writing the system only supports a single build step.

    def __init__(self, job_name=None, script=None):
        self.job_name = job_name
        self.script = script

    def get_builder(self, app=current_app):
        return JenkinsGenericBuilder(
            app=app,
            job_name=self.job_name,
            script=self.script,
        )

    def fetch_artifact(self, step, artifact):
        if artifact['fileName'] == 'jobs.json':
            self._expand_jobs(step, artifact)
        else:
            builder = self.get_builder()
            builder.sync_artifact(step, artifact)

    def _expand_jobs(self, step, artifact):
        builder = self.get_builder()
        artifact_data = builder.fetch_artifact(step, artifact)
        phase_config = artifact_data.json()

        assert phase_config['phase']
        assert phase_config['jobs']

        phase, created = get_or_create(JobPhase, where={
            'job': step.job,
            'project': step.project,
            'label': phase_config['phase'],
        }, defaults={
            'status': Status.queued,
        })

        for job_config in phase_config['jobs']:
            assert job_config['cmd']
            self._expand_job(phase, job_config)

    def _expand_job(self, phase, job_config):
        label = job_config.get('name') or md5(job_config['cmd']).hexdigest()

        step, created = get_or_create(JobStep, where={
            'job': phase.job,
            'project': phase.project,
            'phase': phase,
            'label': label,
        }, defaults={
            'data': {
                'cmd': job_config['cmd'],
                'job_name': self.job_name,
                'build_no': None,
            },
            'status': Status.queued,
        })

        # TODO(dcramer): due to no unique constraints this section of code
        # presents a race condition when run concurrently
        if not step.data.get('build_no'):
            builder = self.get_builder()
            params = builder.get_job_parameters(step.job, script=step.data['cmd'])

            job_data = builder.create_job_from_params(
                job_id=step.id.hex,
                params=params,
                job_name=step.data['job_name'],
            )
            step.data.update(job_data)
            db.session.add(step)
            db.session.commit()

        sync_job_step.delay_if_needed(
            step_id=step.id.hex,
            task_id=step.id.hex,
            parent_task_id=phase.job.id.hex,
        )
