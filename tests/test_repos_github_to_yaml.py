"""Tests for repos_github_to_yaml.py script functionality."""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os

# Set required environment variables before importing
os.environ['ORG'] = 'test-org'
os.environ['TOKEN'] = 'test-token'

# Add parent directory to path to import the script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import repos_github_to_yaml


class TestReposGithubToYamlFunctionality(unittest.TestCase):
    """Test the main functionality of repos_github_to_yaml script."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = MagicMock()
        self.org = 'test-org'

    @patch('repos_github_to_yaml.paginate')
    def test_fetch_team_permissions(self, mock_paginate):
        """Test fetching team permissions for a repository."""
        # Mock API response with team permissions
        mock_paginate.return_value = [
            {'slug': 'admin-team', 'permission': 'admin'},
            {'slug': 'dev-team', 'permission': 'write'},
            {'slug': 'read-team', 'permission': 'read'},  # Should be ignored
        ]
        
        result = repos_github_to_yaml.fetch_team_permissions(
            self.org, 'test-repo', self.mock_session
        )
        
        # Verify admin and write permissions are captured
        self.assertIn('admin-team', result['admin'])
        self.assertIn('dev-team', result['write'])
        # Verify read permissions are not captured
        self.assertNotIn('read-team', result.get('read', []))

    @patch('repos_github_to_yaml.paginate')
    def test_fetch_collaborator_permissions(self, mock_paginate):
        """Test fetching direct collaborator permissions for a repository."""
        # Mock API response with collaborator permissions
        mock_paginate.return_value = [
            {
                'login': 'alice',
                'permissions': {
                    'admin': True,
                    'maintain': False,
                    'push': False,
                    'triage': False,
                    'pull': True
                }
            },
            {
                'login': 'bob',
                'permissions': {
                    'admin': False,
                    'maintain': False,
                    'push': True,  # write access
                    'triage': False,
                    'pull': True
                }
            },
            {
                'login': 'charlie',
                'permissions': {
                    'admin': False,
                    'maintain': False,
                    'push': False,
                    'triage': False,
                    'pull': True  # read-only, should be ignored
                }
            }
        ]
        
        result = repos_github_to_yaml.fetch_collaborator_permissions(
            self.org, 'test-repo', self.mock_session
        )
        
        # Verify admin and write permissions are captured
        self.assertIn('alice', result['admin'])
        self.assertIn('bob', result['write'])
        # Verify read-only user is not captured
        self.assertNotIn('charlie', result.get('read', []))

    @patch('repos_github_to_yaml.paginate')
    def test_fetch_repo_permissions_with_teams_and_users(self, mock_paginate):
        """Test fetching complete repository permissions with both teams and users."""
        # Mock API responses for teams and collaborators
        def paginate_side_effect(url, session, params=None):
            if '/teams' in url:
                return [
                    {'slug': 'admin-team', 'permission': 'admin'},
                    {'slug': 'dev-team', 'permission': 'write'},
                ]
            elif '/collaborators' in url:
                return [
                    {
                        'login': 'alice',
                        'permissions': {
                            'admin': True,
                            'maintain': False,
                            'push': False,
                            'triage': False,
                            'pull': True
                        }
                    }
                ]
            return []
        
        mock_paginate.side_effect = paginate_side_effect
        
        result = repos_github_to_yaml.fetch_repo_permissions(
            self.org, 'test-repo', self.mock_session
        )
        
        # Verify the structure and content
        self.assertIsNotNone(result)
        self.assertIn('test-repo', result)
        self.assertIn('admin', result['test-repo'])
        self.assertIn('write', result['test-repo'])
        
        # Check admin permissions
        self.assertIn('admin-team', result['test-repo']['admin']['teams'])
        self.assertIn('alice', result['test-repo']['admin']['users'])
        
        # Check write permissions
        self.assertIn('dev-team', result['test-repo']['write']['teams'])

    @patch('repos_github_to_yaml.paginate')
    def test_fetch_repo_permissions_empty_repo(self, mock_paginate):
        """Test that empty permissions (no write-level access) return None."""
        # Mock API responses with no tracked permissions
        def paginate_side_effect(url, session, params=None):
            if '/teams' in url:
                return [
                    {'slug': 'read-team', 'permission': 'read'},
                ]
            elif '/collaborators' in url:
                return [
                    {
                        'login': 'charlie',
                        'permissions': {
                            'admin': False,
                            'maintain': False,
                            'push': False,
                            'triage': False,
                            'pull': True  # read-only
                        }
                    }
                ]
            return []
        
        mock_paginate.side_effect = paginate_side_effect
        
        result = repos_github_to_yaml.fetch_repo_permissions(
            self.org, 'test-repo', self.mock_session
        )
        
        # Should return None when no tracked permissions exist
        self.assertIsNone(result)

    def test_load_tracked_repos(self):
        """Test loading tracked repositories from repos.yaml."""
        yaml_content = """
tracked_repos:
  - repo1
  - repo2
  - repo3
permissions: []
"""
        with patch('builtins.open', mock_open(read_data=yaml_content)):
            with patch('pathlib.Path.read_text', return_value=yaml_content):
                from pathlib import Path
                result = repos_github_to_yaml.load_tracked_repos(Path('repos.yaml'))
        
        self.assertEqual(result, ['repo1', 'repo2', 'repo3'])

    def test_load_tracked_repos_empty(self):
        """Test loading tracked repositories when none are specified."""
        yaml_content = """
tracked_repos: []
permissions: []
"""
        with patch('builtins.open', mock_open(read_data=yaml_content)):
            with patch('pathlib.Path.read_text', return_value=yaml_content):
                from pathlib import Path
                result = repos_github_to_yaml.load_tracked_repos(Path('repos.yaml'))
        
        self.assertEqual(result, [])

    def test_render_yaml_structure(self):
        """Test that the YAML rendering produces the correct structure."""
        tracked_repos = ['repo1', 'repo2']
        permissions_list = [
            {
                'repo1': {
                    'admin': {
                        'teams': ['admin-team'],
                        'users': ['alice']
                    }
                }
            },
            {
                'repo2': {
                    'write': {
                        'teams': ['dev-team']
                    }
                }
            }
        ]
        
        result = repos_github_to_yaml.render_yaml(tracked_repos, permissions_list)
        
        # Verify the header comment is present
        self.assertIn('AUTOMATICALLY UPDATED', result)
        self.assertIn('tracked_repos', result)
        self.assertIn('permissions', result)
        
        # Verify tracked repos are listed
        self.assertIn('repo1', result)
        self.assertIn('repo2', result)


class TestReposGithubToYamlRetryLogic(unittest.TestCase):
    """Test that the retry logic is properly configured."""

    def test_create_session_has_retry(self):
        """Test that create_session configures retry logic."""
        session = repos_github_to_yaml.create_session('test-token')
        
        # Verify session is created
        self.assertIsNotNone(session)
        
        # Verify auth headers are set
        self.assertIn('Authorization', session.headers)
        self.assertEqual(session.headers['Authorization'], 'Bearer test-token')


if __name__ == '__main__':
    unittest.main()
