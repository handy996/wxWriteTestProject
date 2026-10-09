"""A rejected guard run must not replace previously published evidence.

Subprocess output is injected; these tests exercise publication refusal, not Java execution.
"""
import contextlib
import importlib.util
import io
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

SPEC = importlib.util.spec_from_file_location('recorder', Path(__file__).with_name('record_guard_binding.py'))
RECORDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECORDER)


class RejectedRunKeepsEvidence(unittest.TestCase):
    def exercise(self, scenario):
        checker = RECORDER.gate()
        sources = checker.read_sources()
        checker.read_sources = lambda: sources
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / 'evidence'
            evidence.mkdir()
            jdk = root / 'jdk'
            (jdk / 'bin').mkdir(parents=True)
            (jdk / 'bin/java').write_text('not executed', encoding='utf-8')
            mvn = root / 'mvn'
            mvn.write_text('not executed', encoding='utf-8')
            reports = root / 'backend/target/surefire-reports'
            reports.mkdir(parents=True)
            fqcn = checker.GUARD_TEST_PACKAGE + '.' + checker.GUARD_TEST_CLASS
            xml = reports / ('TEST-' + fqcn + '.xml')
            shutil.copyfile(checker.SOURCES['guardTestXml'], xml)
            (reports / (fqcn + '.txt')).write_text('injected report', encoding='utf-8')
            census = root / 'backend/target/t03-config-census.txt'
            shutil.copyfile(checker.SOURCES['census'], census)
            suite = ElementTree.parse(xml)
            if scenario in ('failures', 'errors', 'skipped'):
                suite.getroot().set(scenario, '1')
            elif scenario == 'count-mismatch':
                suite.getroot().set('tests', str(int(suite.getroot().get('tests')) + 1))
            suite.write(xml, encoding='utf-8')
            if scenario == 'missing-product':
                census.unlink()
            elif scenario == 'invalid-census':
                census.write_text('invalid census', encoding='utf-8')
            targets = {
                'guardTestXml': evidence / 'T03SessionCookieGuardTest.xml',
                'census': evidence / 'config-census.txt',
                'binding': evidence / 'guard-test-binding.json',
            }
            for target in [*targets.values(), evidence / (checker.GUARD_TEST_CLASS + '.txt')]:
                target.write_bytes(b'previous accepted evidence\r\n')
            before = {p.name: p.read_bytes() for p in evidence.iterdir()}
            checker.SOURCES.update(targets)
            checker.expected_argv = lambda: [str(mvn)]
            # Both the T03-only recorder and the subsequent CI directory option use this fixture.
            checker.use_evidence_directory = lambda _: None
            result = types.SimpleNamespace(returncode=1 if scenario == 'exit-code' else 0, stdout='injected run')
            with patch.multiple(RECORDER, ROOT=root, EVIDENCE=evidence, CENSUS_TARGET=census), \
                    patch.object(RECORDER, 'gate', return_value=checker), \
                    patch.object(RECORDER.subprocess, 'run', return_value=result), \
                    patch('sys.argv', ['record_guard_binding.py', '--jdk', str(jdk)]), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises((SystemExit, checker.Rejected)) as refused:
                    RECORDER.main()
                reason = str(refused.exception)
                if scenario in ('exit-code', 'failures', 'errors', 'skipped'):
                    self.assertIn('not clean', reason)
                elif scenario == 'count-mismatch':
                    self.assertIn('testcase elements', reason)
                elif scenario == 'missing-product':
                    self.assertIn('are absent', reason)
                else:
                    self.assertIsInstance(refused.exception, checker.Rejected)
            self.assertEqual(before, {p.name: p.read_bytes() for p in evidence.iterdir()})

    def test_unclean_run_preserves_published_bytes(self):
        for scenario in ('exit-code', 'failures', 'errors', 'skipped'):
            with self.subTest(scenario=scenario):
                self.exercise(scenario)

    def test_incomplete_proof_preserves_published_bytes(self):
        for scenario in ('missing-product', 'invalid-census', 'count-mismatch'):
            with self.subTest(scenario=scenario):
                self.exercise(scenario)


if __name__ == '__main__':
    unittest.main()
