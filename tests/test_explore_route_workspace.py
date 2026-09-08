import unittest
from dashboard import MainDashboard

class ExploreRouteWorkspaceTests(unittest.TestCase):
    def test_route_entrypoint_opens_html_explore_workspace(self):
        app = MainDashboard.__new__(MainDashboard)
        opened = []
        app._route_to_html_workspace = opened.append
        app.open_exploration_window('route')
        self.assertEqual(opened, ['explore'])

    def test_specialist_actions_route_to_html_workspaces(self):
        app = MainDashboard.__new__(MainDashboard)
        opened = []
        app._route_to_html_workspace = opened.append
        for section in ('mission','recon','ledger','survey'):
            app.open_exploration_window(section)
        self.assertEqual(opened, ['mission','recon','ledger','explore'])
