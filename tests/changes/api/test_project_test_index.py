from uuid import uuid4

from changes.constants import Result, Status
from changes.testutils import APITestCase


class ProjectTestIndexTest(APITestCase):
    def test_simple(self):
        fake_project_id = uuid4()

        build = self.create_build(self.project)
        self.create_job(build)

        project = self.create_project()
        build = self.create_build(project)
        job = self.create_job(
            build, status=Status.finished, result=Result.passed)
        test = self.create_test(job=job, name='foobar')

        path = '/api/0/projects/{0}/tests/'.format(fake_project_id.hex)

        resp = self.client.get(path)
        assert resp.status_code == 404

        path = '/api/0/projects/{0}/tests/?sort=duration'.format(project.id.hex)

        resp = self.client.get(path)
        assert resp.status_code == 200
        data = self.unserialize(resp)
        assert len(data) == 1
        assert data[0]['hash'] == test.name_sha
        assert data[0]['project']['id'] == project.id.hex

        path = '/api/0/projects/{0}/tests/?sort=name'.format(project.id.hex)

        resp = self.client.get(path)
        assert resp.status_code == 200
        data = self.unserialize(resp)
        assert len(data) == 1
        assert data[0]['hash'] == test.name_sha
        assert data[0]['project']['id'] == project.id.hex

        path = '/api/0/projects/{0}/tests/?query=foobar'.format(project.id.hex)

        resp = self.client.get(path)
        assert resp.status_code == 200
        data = self.unserialize(resp)
        assert len(data) == 1
        assert data[0]['hash'] == test.name_sha
        assert data[0]['project']['id'] == project.id.hex

        path = '/api/0/projects/{0}/tests/?query=hello'.format(project.id.hex)

        resp = self.client.get(path)
        assert resp.status_code == 200
        data = self.unserialize(resp)
        assert len(data) == 0
