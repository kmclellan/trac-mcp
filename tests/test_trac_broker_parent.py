"""ChildTicketsPlugin normalization, hierarchy and guarded update regressions."""
import importlib.util
import unittest
from contextlib import contextmanager
from unittest.mock import patch
from pathlib import Path

from trac.test import EnvironmentStub
from trac.ticket.api import TicketSystem as RealTicketSystem
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

    @contextmanager
    def workflow(self, action, changes):
        """Fake workflow controller to exercise effective type and side effects."""
        class Controller:
            side_effects = 0

            def get_ticket_actions(self, req, ticket):
                return [(1, action)]

            def get_ticket_changes(self, req, ticket, selected):
                return dict(changes)

            def apply_action_side_effects(self, req, ticket, selected):
                self.side_effects += 1

        controller = Controller()

        class System:
            def __init__(self, environment):
                self.environment = environment
                self.action_controllers = [controller]

            def get_ticket_fields(self):
                return RealTicketSystem(self.environment).get_ticket_fields()

            def get_available_actions(self, req, ticket):
                return [action]

        with patch.object(broker, "TicketSystem", System), patch.object(
                broker, "workflow_request", return_value=(object(), "test")):
            yield controller

    def change_type(self, ticket_id, new_type, parent_marker=False,
                    action=None):
        fields = {"type": new_type}
        if parent_marker:
            fields["parent"] = ""
        return broker.dispatch_env({
            "op": "ticket_update", "environment": "fixture",
            "ticket_id": ticket_id,
            "expected_changed": broker.td(Ticket(self.environment, ticket_id))["changed"],
            "fields": fields, "action": action,
        }, self.environment, "ticket_update")

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
        for level in range(6):
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


    def test_creation_type_is_independent_of_input_field_order(self):
        self.environment.config.set(
            "childtickets", "parent.defect.restrict_child_type", "task")
        allowed = (
            {"parent": self.parent_id, "type": "task"},
            {"type": "task", "parent": self.parent_id},
        )
        for index, fields in enumerate(allowed):
            with self.subTest(fields=fields):
                result = broker.dispatch_env({
                    "op": "ticket_create", "environment": "fixture",
                    "summary": "ordered child", "idempotency_key": "ordered-%d" % index,
                    "fields": fields,
                }, self.environment, "ticket_create")
                child = Ticket(self.environment, result["ticket"]["id"])
                self.assertEqual("task", child["type"])
                self.assertEqual("#%d" % self.parent_id, child["parent"])
        rejected = (
            {"parent": self.parent_id, "type": "enhancement"},
            {"type": "enhancement", "parent": self.parent_id},
        )
        for index, fields in enumerate(rejected):
            with self.subTest(fields=fields):
                with self.assertRaisesRegex(ValueError, "forbids this child"):
                    broker.dispatch_env({
                        "op": "ticket_create", "environment": "fixture",
                        "summary": "forbidden child",
                        "idempotency_key": "forbidden-ordered-%d" % index,
                        "fields": fields,
                    }, self.environment, "ticket_create")

    def test_existing_parent_revalidated_on_direct_type_update(self):
        self.environment.config.set(
            "childtickets", "parent.defect.restrict_child_type", "task")
        child = self.create(self.parent_id, "child-change-type",
                            extra={"type": "task"})["ticket"]["id"]
        with self.assertRaisesRegex(ValueError, "forbids this child"):
            self.change_type(child, "enhancement")
        self.assertEqual("task", Ticket(self.environment, child)["type"])
        self.assertEqual("#%d" % self.parent_id, Ticket(self.environment, child)["parent"])

    def test_parent_clear_allows_type_change_without_old_link_validation(self):
        self.environment.config.set(
            "childtickets", "parent.defect.restrict_child_type", "task")
        child = self.create(self.parent_id, "child-clear-type",
                            extra={"type": "task"})["ticket"]["id"]
        self.change_type(child, "enhancement", parent_marker=True)
        saved = Ticket(self.environment, child)
        self.assertEqual("", saved["parent"])
        self.assertEqual("enhancement", saved["type"])

    def test_all_retained_parents_revalidated_on_type_change(self):
        second = Ticket(self.environment, self.other_id)
        second["type"] = "task"
        second.save_changes(author="test")
        self.environment.config.set(
            "childtickets", "parent.task.allow_child_tickets", "true")
        self.environment.config.set(
            "childtickets", "parent.defect.restrict_child_type",
            "task, enhancement")
        self.environment.config.set(
            "childtickets", "parent.task.restrict_child_type", "task")
        child = self.create([self.parent_id, self.other_id], "retained-many",
                            extra={"type": "task"})["ticket"]["id"]
        with self.assertRaisesRegex(ValueError, "forbids this child"):
            self.change_type(child, "enhancement")
        self.assertEqual("task", Ticket(self.environment, child)["type"])
        self.assertEqual([self.parent_id, self.other_id],
                         self.relations(child)["parent_ids"])

    def test_workflow_create_uses_final_type_for_validation(self):
        self.environment.config.set(
            "childtickets", "parent.defect.restrict_child_type", "task")
        with self.workflow("create", {"type": "task"}) as controller:
            result = broker.dispatch_env({
                "op": "ticket_create", "environment": "fixture",
                "summary": "workflow type", "idempotency_key": "workflow-final-create",
                "fields": {"parent": self.parent_id, "type": "enhancement"},
                "action": "create",
            }, self.environment, "ticket_create")
        self.assertEqual("task", Ticket(self.environment, result["ticket"]["id"])["type"])
        self.assertEqual(1, controller.side_effects)

    def test_workflow_create_rejects_parent_generation_before_insert(self):
        before = self.environment.db_query("SELECT COUNT(*) FROM ticket")[0][0]
        with self.workflow("create", {"parent": "#%d" % self.parent_id}) as controller:
            with self.assertRaisesRegex(ValueError, "workflow cannot modify parent"):
                broker.dispatch_env({
                    "op": "ticket_create", "environment": "fixture",
                    "summary": "should never exist",
                    "idempotency_key": "reject-workflow-create-parent",
                    "action": "create",
                }, self.environment, "ticket_create")
        self.assertEqual(before, self.environment.db_query("SELECT COUNT(*) FROM ticket")[0][0])
        self.assertEqual(0, controller.side_effects)

    def test_workflow_update_final_type_revalidated_atomically(self):
        self.environment.config.set(
            "childtickets", "parent.defect.restrict_child_type", "task")
        child = self.create(self.parent_id, "workflow-child",
                            extra={"type": "task"})["ticket"]["id"]
        with self.workflow("change", {"type": "enhancement"}) as controller:
            with self.assertRaisesRegex(ValueError, "forbids this child"):
                self.change_type(child, "task", action="change")
        self.assertEqual("task", Ticket(self.environment, child)["type"])
        self.assertEqual(0, controller.side_effects)

    def test_workflow_update_parent_generation_rejected_atomically(self):
        child = self.create(self.parent_id, "workflow-parent-reject")["ticket"]["id"]
        with self.workflow("change", {"parent": "#%d" % self.other_id}) as controller:
            with self.assertRaisesRegex(ValueError, "workflow cannot modify parent"):
                self.change_type(child, "task", action="change")
        self.assertEqual("#%d" % self.parent_id, Ticket(self.environment, child)["parent"])
        self.assertEqual(0, controller.side_effects)

    def test_reparent_depth_includes_every_existing_descendant(self):
        root = self.parent_id
        for index in range(6):
            root = self.create(root, "descendant-depth-%d" % index)["ticket"]["id"]
        # Root A + six descendants is seven nodes. Adding root B above root A
        # must reject, even though root A itself has a shallow new parent path.
        with self.assertRaisesRegex(ValueError, "depth"):
            self.update_parent(self.parent_id, self.other_id)
        self.assertFalse(Ticket(self.environment, self.parent_id)["parent"])

    def test_reparent_descendant_depth_just_within_limit(self):
        root = self.parent_id
        for index in range(5):
            root = self.create(root, "allowed-depth-%d" % index)["ticket"]["id"]
        self.update_parent(self.parent_id, self.other_id)
        self.assertEqual("#%d" % self.other_id,
                         Ticket(self.environment, self.parent_id)["parent"])
        self.assertEqual(1, len(self.relations(root)["parent_ids"]))

    def test_multiple_parent_depth_rejected_for_create_and_update(self):
        deep = self.parent_id
        for index in range(6):
            deep = self.create(deep, "two-branch-depth-%d" % index)["ticket"]["id"]
        with self.assertRaisesRegex(ValueError, "depth"):
            self.create([self.other_id, deep], "multi-depth-invalid")
        shallow = self.create(self.other_id, "shallow-for-reparent")["ticket"]["id"]
        with self.assertRaisesRegex(ValueError, "depth"):
            self.update_parent(shallow, [deep, self.other_id])
        self.assertEqual([self.other_id], self.relations(shallow)["parent_ids"])

    def test_workflow_update_allowed_final_type_override(self):
        self.environment.config.set(
            "childtickets", "parent.defect.restrict_child_type", "task")
        child = self.create(self.parent_id, "allowed-workflow-child",
                            extra={"type": "task"})["ticket"]["id"]
        with self.workflow("change", {"type": "task"}) as controller:
            self.change_type(child, "enhancement", action="change")
        self.assertEqual("task", Ticket(self.environment, child)["type"])
        self.assertEqual([self.parent_id], self.relations(child)["parent_ids"])
        self.assertEqual(1, controller.side_effects)

if __name__ == "__main__":
    unittest.main()
