"""Tests for repos_github_to_yaml.py script functionality."""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Set required environment variables before importing
os.environ['ORG'] = 'test-org'
os.environ['TOKEN'] = 'test-token'

# Add parent directory to path to import the script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import repos_github_to_yaml


class TestFetchCollaboratorPermissions(unittest.TestCase):
    """Test the fetch_collaborator_permissions function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.org = 'test-org'
        self.repo = 'test-repo'

    @patch('repos_github_to_yaml.paginate')
    def test_org_owner_with_implicit_admin_access(self, mock_paginate):
        """Test that org owners with implicit admin access are captured."""
        # Simulate an org owner who has admin access through org role
        mock_paginate.return_value = [
            {
                'login': 'org-owner',
                'permissions': {
                    'admin': True,
                    'maintain': False,
                    'push': True,
                    'triage': False,
                    'pull': True
                }
            }
        ]
        
        result = repos_github_to_yaml.fetch_collaborator_permissions(
            self.org, self.repo, self.mock_session
        )
        
        # Verify the org owner appears in admin level
        self.assertIn('org-owner', result['admin'])
        self.assertEqual(len(result['admin']), 1)
        
        # Verify affiliation=all is used (not direct)
        mock_paginate.assert_called_once()
        call_args = mock_paginate.call_args
        self.assertEqual(call_args[1]['params']['affiliation'], 'all')

    @patch('repos_github_to_yaml.paginate')
    def test_users_with_various_permission_levels(self, mock_paginate):
        """Test that users with different permission levels are correctly categorized."""
        mock_paginate.return_value = [
            {
                'login': 'admin-user',
                'permissions': {'admin': True, 'maintain': False, 'push': True, 'triage': False, 'pull': True}
            },
            {
                'login': 'maintain-user',
                'permissions': {'admin': False, 'maintain': True, 'push': True, 'triage': False, 'pull': True}
            },
            {
                'login': 'write-user',
                'permissions': {'admin': False, 'maintain': False, 'push': True, 'triage': False, 'pull': True}
            },
            {
                'login': 'triage-user',
                'permissions': {'admin': False, 'maintain': False, 'push': False, 'triage': True, 'pull': True}
            },
            {
                'login': 'read-only-user',
                'permissions': {'admin': False, 'maintain': False, 'push': False, 'triage': False, 'pull': True}
            }
        ]
        
        result = repos_github_to_yaml.fetch_collaborator_permissions(
            self.org, self.repo, self.mock_session
        )
        
        # Verify users are in correct permission levels
        self.assertIn('admin-user', result['admin'])
        self.assertIn('maintain-user', result['maintain'])
        self.assertIn('write-user', result['write'])
        self.assertIn('triage-user', result['triage'])
        
        # Verify read-only user is not tracked
        self.assertNotIn('read-only-user', result['admin'])
        self.assertNotIn('read-only-user', result['maintain'])
        self.assertNotIn('read-only-user', result['write'])
        self.assertNotIn('read-only-user', result['triage'])


class TestFetchTeamPermissions(unittest.TestCase):
    """Test the fetch_team_permissions function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.org = 'test-org'
        self.repo = 'test-repo'

    @patch('repos_github_to_yaml.paginate')
    def test_team_permission_mapping_push_to_write(self, mock_paginate):
        """Test that GitHub API 'push' permission is mapped to 'write'."""
        mock_paginate.return_value = [
            {'slug': 'dev-team', 'permission': 'push'},
            {'slug': 'admin-team', 'permission': 'admin'},
            {'slug': 'read-team', 'permission': 'pull'}
        ]
        
        result = repos_github_to_yaml.fetch_team_permissions(
            self.org, self.repo, self.mock_session
        )
        
        # Verify 'push' is mapped to 'write'
        self.assertIn('dev-team', result['write'])
        self.assertIn('admin-team', result['admin'])
        
        # Verify 'pull' (read-only) teams are not tracked
        self.assertNotIn('read-team', result['write'])
        self.assertNotIn('read-team', result['admin'])

    @patch('repos_github_to_yaml.paginate')
    def test_multiple_teams_with_same_permission(self, mock_paginate):
        """Test handling multiple teams with the same permission level."""
        mock_paginate.return_value = [
            {'slug': 'team-a', 'permission': 'push'},
            {'slug': 'team-b', 'permission': 'push'},
            {'slug': 'team-c', 'permission': 'admin'}
        ]
        
        result = repos_github_to_yaml.fetch_team_permissions(
            self.org, self.repo, self.mock_session
        )
        
        # Verify all teams are captured
        self.assertEqual(len(result['write']), 2)
        self.assertIn('team-a', result['write'])
        self.assertIn('team-b', result['write'])
        self.assertIn('team-c', result['admin'])


class TestFetchRepoPermissions(unittest.TestCase):
    """Test the fetch_repo_permissions function."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.org = 'test-org'
        self.repo = 'test-repo'

    @patch('repos_github_to_yaml.fetch_collaborator_permissions')
    @patch('repos_github_to_yaml.fetch_team_permissions')
    def test_combines_teams_and_users(self, mock_fetch_teams, mock_fetch_users):
        """Test that team and user permissions are correctly combined."""
        mock_fetch_teams.return_value = {
            'admin': [],
            'maintain': [],
            'write': ['dev-team'],
            'triage': []
        }
        mock_fetch_users.return_value = {
            'admin': ['org-owner'],
            'maintain': [],
            'write': [],
            'triage': []
        }
        
        result = repos_github_to_yaml.fetch_repo_permissions(
            self.org, self.repo, self.mock_session
        )
        
        # Verify structure
        self.assertIsNotNone(result)
        self.assertIn(self.repo, result)
        
        # Verify admin level has users
        self.assertIn('admin', result[self.repo])
        self.assertIn('users', result[self.repo]['admin'])
        self.assertIn('org-owner', result[self.repo]['admin']['users'])
        
        # Verify write level has teams
        self.assertIn('write', result[self.repo])
        self.assertIn('teams', result[self.repo]['write'])
        self.assertIn('dev-team', result[self.repo]['write']['teams'])

    @patch('repos_github_to_yaml.fetch_collaborator_permissions')
    @patch('repos_github_to_yaml.fetch_team_permissions')
    def test_returns_none_when_no_permissions(self, mock_fetch_teams, mock_fetch_users):
        """Test that None is returned when there are no tracked permissions."""
        mock_fetch_teams.return_value = {
            'admin': [],
            'maintain': [],
            'write': [],
            'triage': []
        }
        mock_fetch_users.return_value = {
            'admin': [],
            'maintain': [],
            'write': [],
            'triage': []
        }
        
        result = repos_github_to_yaml.fetch_repo_permissions(
            self.org, self.repo, self.mock_session
        )
        
        # Verify None is returned for empty permissions
        self.assertIsNone(result)

    @patch('repos_github_to_yaml.fetch_collaborator_permissions')
    @patch('repos_github_to_yaml.fetch_team_permissions')
    def test_sorted_teams_and_users(self, mock_fetch_teams, mock_fetch_users):
        """Test that teams and users are sorted alphabetically."""
        mock_fetch_teams.return_value = {
            'admin': [],
            'maintain': [],
            'write': ['zebra-team', 'alpha-team'],
            'triage': []
        }
        mock_fetch_users.return_value = {
            'admin': ['zulu', 'alice'],
            'maintain': [],
            'write': [],
            'triage': []
        }
        
        result = repos_github_to_yaml.fetch_repo_permissions(
            self.org, self.repo, self.mock_session
        )
        
        # Verify sorting
        self.assertEqual(result[self.repo]['admin']['users'], ['alice', 'zulu'])
        self.assertEqual(result[self.repo]['write']['teams'], ['alpha-team', 'zebra-team'])


class TestLoadTrackedRepos(unittest.TestCase):
    """Test the load_tracked_repos function."""

    @patch('repos_github_to_yaml.Path')
    def test_load_tracked_repos(self, mock_path):
        """Test loading tracked repos from repos.yaml."""
        yaml_content = """tracked_repos:
  - repo1
  - repo2
permissions: []
"""
        mock_path.return_value.read_text.return_value = yaml_content
        
        result = repos_github_to_yaml.load_tracked_repos(mock_path.return_value)
        
        self.assertEqual(result, ['repo1', 'repo2'])

    @patch('repos_github_to_yaml.Path')
    def test_handles_missing_file(self, mock_path):
        """Test handling when repos.yaml doesn't exist."""
        mock_path.return_value.read_text.side_effect = FileNotFoundError()
        
        result = repos_github_to_yaml.load_tracked_repos(mock_path.return_value)
        
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
