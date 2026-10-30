"""ChildTicketsPlugin normalization, hierarchy and guarded update regressions."""
import importlib.util
import unittest
from pathlib import Path

from trac.test import EnvironmentStub
from trac.ticket.model import Ticket

spec = importlib.util.spec_from_file_location(
    "trac_child_parent_broker",
    str(Path(__file__).resolve().parents[1] / "legacy" / "trac_broker_py2.py"),
)
broker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(broker)


class ParentRelationshipTests(unittest.TestCase):
    def setUp(self):
        self.environment = EnvironmentStub(default_data=True, enable=["trac.*"])
        self.environment.config.set("ticket-custom", "parent", "text")
        self.environment.config.set("childtickets", "parent.defect.allow_child_tickets", "true")
        self.parent_id = self.add_ticket("first parent")
        self.other_id = self.add_ticket("second parent")

    def add_ticket(self, summary):
        ticket = Ticket(self.environment)
        ticket["summary"] = summary
        return ticket.insert()

    def create(self, parent, key="parent-create-fixture", extra=None):
        fields = {"parent": parent}
        fields.update(extra or {})
        return broker.dispatch_env({
            "op": "ticket_create",
            "environment": "fixture",
            "summary": "fixture child",
            "description": "bounded test",
            "fields": fields,
            "idempotency_key": key,
        }, self.environment, "ticket_create")

    def update_parent(self, ticket_id, parent):
        return broker.dispatch_env({
            "op": "ticket_update",
            "environment": "fixture",
            "ticket_id": ticket_id,
            "expected_changed": broker.td(Ticket(self.environment, ticket_id))["changed"],
            "fields": {"parent": parent},
        }, self.environment, "ticket_update")

    def relations(self, ticket_id):
        return broker.dispatch_env({
            "op": "ticket_relations",
            "environment": "fixture",
            "ticket_id": ticket_id,
        }, self.environment, "ticket_relations")

    def test_numeric_and_hash_creation_canonicalize_and_replay(self):
        for index, value in enumerate((self.parent_id, str(self.parent_id), "#%d" % self.parent_id)):
            with self.subTest(value=value):
                key = "numeric-create-%d" % index
                first = self.create(value, key)
                again = self.create(value, key)
                self.assertFalse(first["duplicate"])
                self.assertTrue(again["duplicate"])
                child_id = first["ticket"]["id"]
                self.assertEqual("#%d" % self.parent_id,
                                 Ticket(self.environment, child_id)["parent"])
                self.assertEqual([self.parent_id], self.relations(child_id)["parent_ids"])

    def test_multiple_parents_and_reverse_children(self):
        child = self.create([self.parent_id, "#%d" % self.other_id],
                            "multi-parents-create")["ticket"]["id"]
        value = "#%d #%d" % (self.parent_id, self.other_id)
        self.assertEqual(value, Ticket(self.environment, child)["parent"])
        self.assertEqual([self.parent_id, self.other_id], self.relations(child)["parent_ids"])
        self.assertIn(child, self.relations(self.parent_id)["child_ids"])
        self.assertIn(child, self.relations(self.other_id)["child_ids"])

    def test_reparent_and_clear_and_stale_revision(self):
        child = self.create(self.parent_id, "reparent-create")["ticket"]["id"]
        stale = broker.td(Ticket(self.environment, child))["changed"]
        moved = self.update_parent(child, self.other_id)
        self.assertFalse(moved["duplicate"])
        self.assertEqual("#%d" % self.other_id, Ticket(self.environment, child)["parent"])
        self.assertNotIn(child, self.relations(self.parent_id)["child_ids"])
        self.assertIn(child, self.relations(self.other_id)["child_ids"])
        with self.assertRaisesRegex(ValueError, "stale ticket revision"):
            broker.dispatch_env({
                "op": "ticket_update", "environment": "fixture", "ticket_id": child,
                "expected_changed": stale, "fields": {"parent": self.parent_id},
            }, self.environment, "ticket_update")
        self.update_parent(child, "")
        self.assertEqual("", Ticket(self.environment, child)["parent"])
        self.assertEqual([], self.relations(child)["parent_ids"])

    def test_cycle_and_self_parent_rejected(self):
        child = self.create(self.parent_id, "cycle-create")["ticket"]["id"]
        for node, parent in ((child, child), (self.parent_id, child)):
            with self.subTest(node=node):
                with self.assertRaisesRegex(ValueError, "self|cycle"):
                    self.update_parent(node, parent)
        self.assertFalse(Ticket(self.environment, self.parent_id)["parent"])

    def test_bad_references_rejected_without_ticket_mutation(self):
        invalid = ("#0", "0", "-1", "26.1", "##1", "1,#2",
                   "1 #2garbage", "x", "#999999999999999999", 99999,
                   True, False, 1.5, [self.parent_id, self.parent_id])
        for index, value in enumerate(invalid):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "parent"):
                    self.create(value, "bad-reference-%d" % index)

    def test_plugin_parent_permissions_and_restrictions(self):
        self.environment.config.set(
            "childtickets", "parent.defect.allow_child_tickets", "false")
        with self.assertRaisesRegex(ValueError, "does not allow child"):
            self.create(self.parent_id, "disallowed-parent")
        self.environment.config.set(
            "childtickets", "parent.defect.allow_child_tickets", "true")
        self.environment.config.set(
            "childtickets", "parent.defect.restrict_child_type", "task")
        with self.assertRaisesRegex(ValueError, "forbids this child"):
            self.create(self.parent_id, "wrong-child-type")
        self.environment.config.set(
            "childtickets", "parent.defect.restrict_child_type", "")
        parent = Ticket(self.environment, self.parent_id)
        parent["status"] = "closed"
        parent.save_changes(author="test")
        with self.assertRaisesRegex(ValueError, "parent ticket is closed"):
            self.create(self.parent_id, "closed-parent")

    def test_plugin_depth_limit_enforced(self):
        parent_id = self.parent_id
        for level in range(7):
            parent_id = self.create(parent_id, "depth-%d" % level)["ticket"]["id"]
        with self.assertRaisesRegex(ValueError, "depth"):
            self.create(parent_id, "too-deep")

    def test_open_child_prevents_parent_resolution(self):
        child_id = self.create(self.parent_id, "unresolved-child")["ticket"]["id"]
        with self.assertRaisesRegex(ValueError, "child ticket"):
            broker.require_closed_children_before_resolve(self.environment, self.parent_id)
        child = Ticket(self.environment, child_id)
        child["status"] = "closed"
        child.save_changes(author="test")
        broker.require_closed_children_before_resolve(self.environment, self.parent_id)

    def test_unlisted_custom_field_denied(self):
        with self.assertRaisesRegex(ValueError, "field not allowed"):
            self.create(self.parent_id, "bad-field", {"arbitrary": "yes"})

    def test_parent_not_configured_rejected(self):
        env = EnvironmentStub(default_data=True, enable=["trac.*"])
        old = self.environment
        self.environment = env
        try:
            with self.assertRaisesRegex(ValueError, "parent field not configured"):
                self.create(self.parent_id, "missing-field")
            with self.assertRaisesRegex(ValueError, "parent field not configured"):
                self.relations(self.parent_id)
        finally:
            self.environment = old

    def test_invalid_update_is_atomic(self):
        child = self.create(self.parent_id, "atomic-create")["ticket"]["id"]
        with self.assertRaisesRegex(ValueError, "parent"):
            self.update_parent(child, "9999999")
        self.assertEqual("#%d" % self.parent_id,
                         Ticket(self.environment, child)["parent"])


if __name__ == "__main__":
    unittest.main()
