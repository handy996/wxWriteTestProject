"""Regression checks for moved checkouts and Windows/Linux Cookie execution records."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('cookie_gate', Path(__file__).with_name('check_session_cookie.py'))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class CookieCommandPortabilityTest(unittest.TestCase):
    def test_relative_record_survives_a_different_checkout(self):
        record = {'command': gate.expected_argv(portable=True)}
        root = Path('/home/runner/work/other/other')
        with patch.multiple(gate, ROOT=root,
                            MVN=root / '.tools/t02/apache-maven-3.9.11/bin/mvn',
                            REPO=root / '.tools/t02/m2'):
            gate.argv_check(record, 'binding')

    def test_old_absolute_record_survives_checkout_and_platform_changes(self):
        for root, suffix in [('E:/old checkout/wxAgent', '.cmd'), ('/home/runner/work/old/old', '')]:
            with self.subTest(root=root):
                command = gate.expected_argv(portable=True)
                command[0] = root + '/.tools/t02/apache-maven-3.9.11/bin/mvn' + suffix
                command[6] = '-Dmaven.repo.local=' + root + '/.tools/t02/m2'
                gate.argv_check({'command': command}, 'binding')

    def test_a_repository_from_another_root_is_rejected(self):
        command = gate.expected_argv(portable=True)
        command[0] = 'E:/checkout/.tools/t02/apache-maven-3.9.11/bin/mvn.cmd'
        command[6] = '-Dmaven.repo.local=E:/unrelated/.tools/t02/m2'
        with self.assertRaises(gate.Rejected):
            gate.argv_check({'command': command}, 'binding')

    def test_non_pinned_execution_cannot_hide_behind_normalization(self):
        pinned = gate.expected_argv(portable=True)
        for command in (['echo'] + pinned,
                        pinned + ['-Dsurefire.failIfNoSpecifiedTests=false'],
                        [pinned[0].replace('3.9.11', '3.8.8')] + pinned[1:]):
            with self.subTest(command=command):
                with self.assertRaises(gate.Rejected):
                    gate.argv_check({'command': command}, 'binding')


if __name__ == '__main__':
    unittest.main()
