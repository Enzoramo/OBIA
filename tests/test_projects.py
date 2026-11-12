"""Portable routing and installation, confined to temporary directories."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/obia/scripts'))
import obia
import projects
import setup_obia


class ProjectTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='obia-projects-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.vaults = self.root / 'Private vaults'
        self.vaults.mkdir()
        self.config = self.root / 'config/projects.json'
        projects.configure(self.vaults, self.config)

    def project(self, name='Example'):
        path = self.root / name
        path.mkdir(parents=True)
        return path

    def test_separate_projects_subfolders_and_duplicate_names(self):
        first = self.project('first/Same')
        a = projects.ensure(first, config_path=self.config)
        child = first / 'src'
        child.mkdir()
        self.assertEqual(projects.resolve(child, self.config)['vault'], a['vault'])
        b = projects.ensure(self.project('second/Same'), config_path=self.config)
        self.assertNotEqual(a['project'], b['project'])
        self.assertNotEqual(a['vault'], b['vault'])
        self.assertTrue((Path(a['vault']) / '.obsidian').is_dir())
        self.assertFalse(projects.ensure(first, config_path=self.config)['created'])

    @unittest.skipUnless(shutil.which('git'), 'Git is optional')
    def test_worktree_recovers_the_main_repository_vault(self):
        main = self.project('repository')
        def git(*args):
            subprocess.run(['git', '-C', str(main), *args], check=True, capture_output=True)
        git('init')
        git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-m', 'initial')
        worktree = self.root / 'parallel-worktree'
        git('worktree', 'add', '-b', 'parallel', str(worktree))
        a = projects.ensure(main, config_path=self.config)
        self.assertEqual(projects.ensure(worktree, config_path=self.config)['vault'], a['vault'])

    def test_missing_registered_vault_and_parent_are_not_recreated(self):
        path = self.project()
        entry = projects.ensure(path, config_path=self.config)
        shutil.rmtree(entry['vault'])
        with self.assertRaisesRegex(ValueError, 'missing'):
            projects.ensure(path, config_path=self.config)
        self.assertFalse(Path(entry['vault']).exists())
        self.vaults.rmdir()
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            projects.ensure(path, config_path=self.config)
        self.assertFalse(self.vaults.exists())

    def test_unrelated_folder_and_registry_conflicts_are_preserved(self):
        unrelated = self.vaults / 'OBIA - Example'
        unrelated.mkdir()
        (unrelated / 'human.md').write_text('keep', encoding='utf-8')
        entry = projects.ensure(self.project(), config_path=self.config)
        self.assertNotEqual(Path(entry['vault']), unrelated)
        self.assertEqual((unrelated / 'human.md').read_text(), 'keep')
        with projects.locked(self.config):
            with self.assertRaisesRegex(ValueError, 'locked'):
                projects.ensure(self.root, config_path=self.config)
        self.assertFalse((self.config.parent / '.projects.lock').exists())

    def test_vault_identity_cannot_be_substituted(self):
        path = self.project()
        entry = projects.ensure(path, config_path=self.config)
        (Path(entry['vault']) / '.obia-project.json').write_text('{}')
        with self.assertRaises(ValueError):
            projects.resolve(path, self.config)
        with self.assertRaises(ValueError):
            projects.ensure(path, config_path=self.config)

    def test_install_update_preserves_registry_instructions_and_backup(self):
        source = Path(setup_obia.__file__).resolve().parents[1]
        destination = self.root / 'skills/obia'
        instructions = self.root / 'AGENTS.md'
        instructions.write_text('# Human instructions\nKeep this.\n', encoding='utf-8')
        entry = projects.ensure(self.project(), config_path=self.config)
        registry_before = self.config.read_bytes()
        setup_obia.install(source, destination, self.config.parent, self.vaults, instructions, dependencies=False)
        with self.assertRaisesRegex(ValueError, '--update'):
            setup_obia.install(source, destination, self.config.parent, self.vaults, instructions, dependencies=False)
        result = setup_obia.install(source, destination, self.config.parent, self.vaults, instructions, update=True, dependencies=False)
        self.assertTrue(Path(result['backup']).is_dir())
        self.assertEqual(self.config.read_bytes(), registry_before)
        self.assertIn('Keep this.', instructions.read_text())
        self.assertEqual(instructions.read_text().count(setup_obia.START), 1)
        self.assertTrue(Path(entry['vault']).is_dir())
        recovered = subprocess.run([sys.executable, str(destination / 'scripts/projects.py'), '--config-dir', str(self.config.parent), 'resolve', '--path', entry['root']], capture_output=True, text=True, encoding='utf-8', check=True)
        self.assertEqual(json.loads(recovered.stdout)['vault'], entry['vault'])

    def test_dependency_failure_does_not_replace_installed_code(self):
        source = Path(setup_obia.__file__).resolve().parents[1]
        destination = self.root / 'skills/obia'
        setup_obia.install(source, destination, self.config.parent, self.vaults, dependencies=False)
        before = (destination / 'scripts/obia.py').read_bytes()
        with patch.object(setup_obia.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['pip'])):
            with self.assertRaises(subprocess.CalledProcessError):
                setup_obia.install(source, destination, self.config.parent, self.vaults, update=True)
        self.assertEqual((destination / 'scripts/obia.py').read_bytes(), before)
        self.assertEqual(list(destination.parent.glob('.obia-install-*')), [])

    def test_installer_refuses_relocation_and_unowned_target(self):
        source = Path(setup_obia.__file__).resolve().parents[1]
        destination = self.root / 'skills/obia'
        destination.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'not an OBIA'):
            setup_obia.install(source, destination, self.config.parent, self.vaults, update=True, dependencies=False)
        other = self.root / 'other vaults'
        other.mkdir()
        with self.assertRaisesRegex(ValueError, 'differs'):
            projects.configure(other, self.config)
