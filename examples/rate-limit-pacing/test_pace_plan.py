import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import pace_plan

FIXTURES = Path(__file__).parent / 'fixtures'


def run(argv):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = pace_plan.main(argv)
    return code, buffer.getvalue()


def run_json(argv):
    code, text = run(argv)
    return code, json.loads(text)


def write(payload):
    handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
    json.dump(payload, handle)
    handle.close()
    return handle.name


class LimitsTests(unittest.TestCase):
    def test_all_plans_resolve(self):
        for plan in ('Free', 'Starter', 'Pro', 'Scale'):
            limits, basis = pace_plan.resolve_limits({'plan': plan})
            self.assertEqual(basis, f'plan {plan}')
            self.assertGreaterEqual(limits['rpm'], 1)

    def test_plan_is_case_insensitive(self):
        limits, basis = pace_plan.resolve_limits({'plan': 'starter'})
        self.assertEqual(basis, 'plan Starter')
        self.assertEqual(limits['rpm'], 60)

    def test_unknown_plan_is_input_error(self):
        with self.assertRaises(pace_plan.InputError):
            pace_plan.resolve_limits({'plan': 'Enterprise'})

    def test_explicit_limits_without_plan(self):
        limits, basis = pace_plan.resolve_limits({'limits': {'rpm': 10, 'rpd': 100, 'concurrency': 3}})
        self.assertEqual(limits, {'rpm': 10, 'rpd': 100, 'concurrency': 3})
        self.assertEqual(basis, 'explicit limits')

    def test_explicit_limit_overrides_plan(self):
        limits, _ = pace_plan.resolve_limits({'plan': 'Free', 'limits': {'rpm': 999}})
        self.assertEqual(limits['rpm'], 999)
        self.assertEqual(limits['rpd'], 1000)

    def test_missing_limit_is_input_error(self):
        with self.assertRaises(pace_plan.InputError):
            pace_plan.resolve_limits({'limits': {'rpm': 10}})

    def test_zero_limit_is_input_error(self):
        with self.assertRaises(pace_plan.InputError):
            pace_plan.resolve_limits({'limits': {'rpm': 0, 'rpd': 1, 'concurrency': 1}})

    def test_boolean_limit_is_input_error(self):
        with self.assertRaises(pace_plan.InputError):
            pace_plan.resolve_limits({'limits': {'rpm': True, 'rpd': 1, 'concurrency': 1}})


class RequestParsingTests(unittest.TestCase):
    def test_missing_requests_is_error(self):
        with self.assertRaises(pace_plan.InputError):
            pace_plan.resolve_requests({}, 0)

    def test_empty_requests_is_error(self):
        with self.assertRaises(pace_plan.InputError):
            pace_plan.resolve_requests({'requests': []}, 0)

    def test_duplicate_id_is_error(self):
        data = {'requests': [{'id': 'a'}, {'id': 'a'}]}
        with self.assertRaises(pace_plan.InputError):
            pace_plan.resolve_requests(data, 0)

    def test_missing_id_is_error(self):
        with self.assertRaises(pace_plan.InputError):
            pace_plan.resolve_requests({'requests': [{}]}, 0)

    def test_default_duration_applied(self):
        data = {'requests': [{'id': 'a'}]}
        parsed = pace_plan.resolve_requests(data, 7)
        self.assertEqual(parsed[0]['duration_seconds'], 7)

    def test_request_duration_overrides_default(self):
        data = {'requests': [{'id': 'a', 'duration_seconds': 2}]}
        parsed = pace_plan.resolve_requests(data, 7)
        self.assertEqual(parsed[0]['duration_seconds'], 2)

    def test_negative_duration_is_error(self):
        data = {'requests': [{'id': 'a', 'duration_seconds': -1}]}
        with self.assertRaises(pace_plan.InputError):
            pace_plan.resolve_requests(data, 0)


class ValidateTests(unittest.TestCase):
    def test_valid_schedule_exit_zero(self):
        code, report = run_json([str(FIXTURES / 'valid-schedule.json')])
        self.assertEqual(code, 0)
        self.assertEqual(report['status'], 'valid')
        self.assertEqual(report['limits'], {'rpm': 60, 'rpd': 5000, 'concurrency': 4})

    def test_minute_violation_exit_one(self):
        code, report = run_json([str(FIXTURES / 'minute-violation.json')])
        self.assertEqual(code, 1)
        self.assertEqual(report['status'], 'invalid')
        self.assertEqual(report['observed']['max_per_minute'], 31)
        self.assertEqual(report['violations'][0]['kind'], 'rpm')

    def test_concurrency_violation_exit_one(self):
        code, report = run_json([str(FIXTURES / 'concurrency-violation.json')])
        self.assertEqual(code, 1)
        self.assertEqual(report['observed']['max_concurrent'], 3)
        self.assertEqual(report['violations'][0]['kind'], 'concurrency')

    def test_daily_violation_exit_one(self):
        code, report = run_json([str(FIXTURES / 'daily-violation.json')])
        self.assertEqual(code, 1)
        self.assertEqual(report['violations'][0]['kind'], 'rpd')

    def test_minute_boundary_is_valid(self):
        path = write({'limits': {'rpm': 2, 'rpd': 100, 'concurrency': 5},
                      'requests': [{'id': 'a', 'at_second': 0}, {'id': 'b', 'at_second': 59}]})
        code, report = run_json([path])
        self.assertEqual(code, 0)
        self.assertEqual(report['observed']['max_per_minute'], 2)

    def test_window_is_half_open(self):
        path = write({'limits': {'rpm': 1, 'rpd': 100, 'concurrency': 5},
                      'requests': [{'id': 'a', 'at_second': 0}, {'id': 'b', 'at_second': 60}]})
        code, report = run_json([path])
        self.assertEqual(code, 0)
        self.assertEqual(report['observed']['max_per_minute'], 1)

    def test_concurrency_boundary_is_valid(self):
        path = write({'limits': {'rpm': 100, 'rpd': 100, 'concurrency': 2},
                      'duration_seconds': 10,
                      'requests': [{'id': 'a', 'at_second': 0}, {'id': 'b', 'at_second': 1}]})
        code, _ = run_json([path])
        self.assertEqual(code, 0)

    def test_zero_duration_never_overlaps(self):
        path = write({'limits': {'rpm': 100, 'rpd': 100, 'concurrency': 1},
                      'requests': [{'id': 'a', 'at_second': 0}, {'id': 'b', 'at_second': 0}]})
        code, report = run_json([path])
        self.assertEqual(code, 0)
        self.assertEqual(report['observed']['max_concurrent'], 0)

    def test_missing_at_second_exit_two(self):
        code, report = run_json([str(FIXTURES / 'error-missing-at.json')])
        self.assertEqual(code, 2)
        self.assertEqual(report['status'], 'error')

    def test_negative_at_second_exit_two(self):
        path = write({'plan': 'Starter', 'requests': [{'id': 'a', 'at_second': -1}]})
        code, _ = run_json([path])
        self.assertEqual(code, 2)

    def test_invalid_json_exit_two(self):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        handle.write('{not json')
        handle.close()
        code, report = run_json([handle.name])
        self.assertEqual(code, 2)
        self.assertIn('invalid JSON', report['error'])

    def test_non_object_top_level_exit_two(self):
        path = write([1, 2, 3])
        code, _ = run_json([path])
        self.assertEqual(code, 2)

    def test_missing_file_exit_two(self):
        code, report = run_json([str(FIXTURES / 'does-not-exist.json')])
        self.assertEqual(code, 2)
        self.assertIn('cannot read', report['error'])

    def test_text_format_valid(self):
        code, text = run(['--format', 'text', str(FIXTURES / 'valid-schedule.json')])
        self.assertEqual(code, 0)
        self.assertIn('pace_plan validate: valid', text)


class ScheduleTests(unittest.TestCase):
    def test_burst_is_spaced_by_minute(self):
        code, report = run_json(['--mode', 'schedule', str(FIXTURES / 'schedule-burst.json')])
        self.assertEqual(code, 0)
        starts = [row['start_second'] for row in report['schedule']]
        self.assertEqual(starts, [0, 0, 60, 60, 120])
        self.assertEqual(report['makespan_seconds'], 120)
        self.assertEqual(report['observed']['max_per_minute'], 2)

    def test_concurrency_pushes_start(self):
        code, report = run_json(['--mode', 'schedule', str(FIXTURES / 'schedule-concurrency.json')])
        self.assertEqual(code, 0)
        starts = [row['start_second'] for row in report['schedule']]
        self.assertEqual(starts, [0, 0, 10, 10])
        self.assertEqual(report['observed']['max_concurrent'], 2)

    def test_schedule_rolls_to_next_day(self):
        path = write({'limits': {'rpm': 100, 'rpd': 2, 'concurrency': 5},
                      'requests': [{'id': f'x{i}'} for i in range(5)]})
        code, report = run_json(['--mode', 'schedule', path])
        self.assertEqual(code, 0)
        starts = [row['start_second'] for row in report['schedule']]
        self.assertEqual(starts, [0, 0, 86400, 86400, 172800])
        self.assertTrue(report['warnings'])

    def test_infeasible_past_horizon(self):
        path = write({'limits': {'rpm': 1, 'rpd': 1, 'concurrency': 1},
                      'requests': [{'id': f'x{i}'} for i in range(400)]})
        code, report = run_json(['--mode', 'schedule', path])
        self.assertEqual(code, 1)
        self.assertEqual(report['status'], 'infeasible')

    def test_schedule_is_deterministic(self):
        first = run_json(['--mode', 'schedule', str(FIXTURES / 'schedule-concurrency.json')])[1]
        second = run_json(['--mode', 'schedule', str(FIXTURES / 'schedule-concurrency.json')])[1]
        self.assertEqual(first, second)

    def test_schedule_respects_limits(self):
        code, report = run_json(['--mode', 'schedule', str(FIXTURES / 'schedule-burst.json')])
        limits = report['limits']
        observed = report['observed']
        self.assertLessEqual(observed['max_per_minute'], limits['rpm'])
        self.assertLessEqual(observed['max_per_day'], limits['rpd'])
        self.assertLessEqual(observed['max_concurrent'], limits['concurrency'])


if __name__ == '__main__':
    unittest.main()
