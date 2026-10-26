"""Broker request lifecycle tests without requiring an installed Trac runtime."""

import ast
from pathlib import Path
import unittest


def load_request_handlers():
    """Compile the actual dispatch functions without importing Trac plugins."""
    path = Path(__file__).resolve().parents[1] / "legacy" / "trac_broker_py2.py"
    source = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = ("dispatch", "dispatch_env")
    functions = [
        node for node in source.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    if {node.name for node in functions} != set(names):
        raise AssertionError("Broker request handlers not found")
    module = ast.Module(body=functions, type_ignores=[])
    scope = {"ENVS": {"fixture": "/generic/fixture"},
             "trac_version": "fixture-version", "simple": lambda value: value}
    exec(compile(module, str(path), "exec"), scope)
    return scope


class FakeEnvironment:
    project_name = "Fixture"

    def __init__(self):
        self.shutdown_calls = 0

    def shutdown(self):
        self.shutdown_calls += 1


class TracBrokerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.handlers = load_request_handlers()
        self.environment = FakeEnvironment()
        self.handlers["env"] = lambda name: self.environment

    def test_successful_request_closes_environment(self):
        result = self.handlers["dispatch"]({"op": "ping", "environment": "fixture"})
        self.assertEqual(result["trac_version"], "fixture-version")
        self.assertEqual(self.environment.shutdown_calls, 1)

    def test_failed_request_closes_environment(self):
        with self.assertRaisesRegex(ValueError, "unknown operation"):
            self.handlers["dispatch"]({"op": "invalid-operation",
                                       "environment": "fixture"})
        self.assertEqual(self.environment.shutdown_calls, 1)

    def test_environment_listing_does_not_open_environment(self):
        def unexpected(_name):
            self.fail("An environment should not be opened for listing")
        self.handlers["env"] = unexpected
        result = self.handlers["dispatch"]({"op": "environments"})
        self.assertEqual(result["environments"], ["fixture"])


if __name__ == "__main__":
    unittest.main()
