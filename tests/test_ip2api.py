# flake8: noqa
import argparse
import unittest
import uuid
import sys
import os

sys.path.append(os.path.dirname(sys.path[0]))
from ip2api import IP2, IP2Project, IP2Experiment, IP2Database, IP2Instrument, IP2Organism

PROJECT_NAME = 'ip2api_test'
TEMPORARY_PROJECT_NAME = '{}_{}'.format(PROJECT_NAME, uuid.uuid4().hex)
EXPERIMENT_NAME = 'test_experiment'
TEMPORARY_EXPERIMENT_NAME = '{}_{}'.format(EXPERIMENT_NAME, uuid.uuid4().hex)
TEST_INSTANCE_URL = 'http://goldfish.scripps.edu'

class TestIP2API(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Setup ip2 instance to be shared by all tests."""
        cls.ip2 = IP2(
            ip2_url=TEST_INSTANCE_URL,
            username=args.username,
            password=args.password,
            default_project_name=PROJECT_NAME,
            helper_experiment_name=EXPERIMENT_NAME
        )

    # test authenticatin
    def test_login(self):
        self.assertTrue(self.ip2.login(args.password, force=True))

    def test_logout(self):
        self.assertTrue(self.ip2.logout())

    # test project and experiment handling
    # first check that we can get a handle to the default project
    def test_get_project_id(self):
        self.assertGreater(self.ip2.get_default_project().id, 0)

    # test that we can get a handle to the helper experiment
    # which is required by some methods
    def test_get_experiment_id(self):
        self.assertGreater(self.ip2.get_helper_experiment().id, 0)

    def test_get_experiment_path(self):
        experiment = self.ip2.get_helper_experiment()
        self.assertIsInstance(experiment.path, str)

    # test that we can create a project, add experiments, and then clean up successfully
    def test_create_project(self):
        project = IP2Project(
            self.ip2,
            name=self._get_temp_name(PROJECT_NAME)
        )

        self.assertTrue(project.create())
        # check that the temp project has an id
        self.assertGreater(project.id, 0)
        # check that we have no experiments added to the new project
        self.assertEqual(len(project.experiments), 0)

        # make sure we clean-up this project
        self.addCleanup(project.delete)

    def test_create_experiment(self):
        project = self._get_temp_project()
        experiment = project.add_experiment(
            name=TEMPORARY_EXPERIMENT_NAME
        )

        self.assertGreater(experiment.id, 0)
        self.assertEqual(len(project.experiments), 1)
        self.addCleanup(project.delete)

    # test that removal of experiment and projects works
    def test_delete_experiment(self):
        project = self._get_temp_project()
        experiment = self._get_temp_experiment()
        self.assertTrue(experiment.delete())
        self.assertEqual(len(project.experiments), 0)
        self.addCleanup(project.delete)

    def test_delete_project(self):
        project = self._get_temp_project()
        self.assertTrue(project.delete())

    # test actual search functionality
    def test_upload_spectra(self):
        pass

    def test_get_dtaselect(self):
        pass

    def test_prolucid_search(self):
        pass

    def test_check_job_status(self):
        pass

    # Test organism functionality
    def test_get_organism(self):
        human = IP2Organism(self.ip2, name='Human')
        self.assertIn(human, self.ip2.organisms)

    # Test instrument functionality
    def test_get_instrument(self):
        self.assertIn('LTQ', (i.name for i in self.ip2.instruments))

    # Utility methods
    def _get_temp_project(self):
        project = self.ip2.get_project(TEMPORARY_PROJECT_NAME)

        if not project:
            project = IP2Project(self.ip2, name=TEMPORARY_PROJECT_NAME)
            project.create()

        return project

    def _get_temp_experiment(self):
        project = self._get_temp_project()
        experiment = project.get_experiment(TEMPORARY_EXPERIMENT_NAME)

        if not experiment:
            experiment = IP2Experiment(self.ip2, project, name=TEMPORARY_EXPERIMENT_NAME)
            experiment.create()

        return experiment

    def _get_temp_name(self, root):
        return '{}_{}'.format(root, uuid.uuid4().hex)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('username')
    parser.add_argument('password')
    parser.add_argument('unittest_args', nargs='*')
    args = parser.parse_args()
    sys.argv[1:] = args.unittest_args
    unittest.main()
