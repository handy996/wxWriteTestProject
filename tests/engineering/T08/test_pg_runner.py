"""The CI result gate must reject green Maven runs that skipped database coverage."""
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('cost_runner', Path(__file__).with_name('run_pg.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def suite(name, count, skipped=0, errors=0):
    return {'suite': 'com.example.editorial.cost.' + name, 'tests': count, 'failures': 0,
            'errors': errors, 'skipped': skipped, 'cases': [f'test{i}' for i in range(count)]}


class CostResultGateTest(unittest.TestCase):
    def setUp(self):
        self.args = SimpleNamespace(expect_tests=65, expect_skipped=0,
                                    tests='CostPricingTest,T08PostgresTest')

    def test_all_65_cases_actually_execute(self):
        totals, problems = runner.judge_suites([suite('CostPricingTest', 28), suite('T08PostgresTest', 37)],
                                               self.args)
        self.assertEqual({'tests': 65, 'failures': 0, 'skipped': 0}, totals)
        self.assertEqual([], problems)

    def test_a_green_but_disabled_database_suite_is_rejected(self):
        _totals, problems = runner.judge_suites([suite('CostPricingTest', 28),
                                                suite('T08PostgresTest', 37, skipped=37)], self.args)
        self.assertTrue(any('skipped 37' in problem for problem in problems))

    def test_empty_and_missing_database_reports_are_rejected(self):
        for suites in ([], [suite('CostPricingTest', 65)]):
            with self.subTest(suites=suites):
                _totals, problems = runner.judge_suites(suites, self.args)
                self.assertTrue(any('no Surefire report for' in problem for problem in problems))

    def test_errors_and_fabricated_counts_are_rejected(self):
        for live in (suite('T08PostgresTest', 37, errors=1),
                     dict(suite('T08PostgresTest', 37), cases=[])):
            with self.subTest(live=live):
                _totals, problems = runner.judge_suites([suite('CostPricingTest', 28), live], self.args)
                self.assertTrue(problems)

    def test_method_filters_still_identify_the_reported_class(self):
        self.args.tests = 'CostPricingTest#example,T08PostgresTest#another'
        _totals, problems = runner.judge_suites([suite('CostPricingTest', 28), suite('T08PostgresTest', 37)], self.args)
        self.assertEqual([], problems)


if __name__ == '__main__':
    unittest.main()
