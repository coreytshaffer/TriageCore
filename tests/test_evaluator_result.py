import unittest
import json
import tempfile
import os

from triage_core.evaluator_result import (
    validate_evaluator_result,
    load_evaluator_result,
    EvaluatorResultValidationError
)

class TestEvaluatorResult(unittest.TestCase):
    def setUp(self):
        self.valid_data = {
            "result_type": "workspace_packet_evaluation_result",
            "item_id": "DEMO-001",
            "packet_id": "workspace_eval_packet_contract_001",
            "decision": "observe",
            "approval_status": "not_approval",
            "target_invocation": "not_invoked",
            "score": "pass",
            "reasons": ["Test reason 1", "Test reason 2"],
            "warnings": ["Test warning"],
            "generated_at": "2026-06-27T00:00:00Z"
        }

    def test_valid_observation_result_loads(self):
        result = validate_evaluator_result(self.valid_data)
        self.assertEqual(result.item_id, "DEMO-001")
        self.assertEqual(result.approval_status, "not_approval")
        self.assertEqual(result.target_invocation, "not_invoked")
        self.assertEqual(result.decision, "observe")
        self.assertEqual(result.score, "pass")
        self.assertEqual(len(result.reasons), 2)
        self.assertEqual(len(result.warnings), 1)

    def test_malformed_json_returns_error(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".json") as tf:
            tf.write("{ this is not valid json")
            tf_path = tf.name
            
        try:
            with self.assertRaises(EvaluatorResultValidationError) as context:
                load_evaluator_result(tf_path)
            self.assertIn("Malformed JSON", str(context.exception))
        finally:
            os.unlink(tf_path)

    def test_missing_required_field_returns_error(self):
        del self.valid_data["item_id"]
        with self.assertRaises(EvaluatorResultValidationError) as context:
            validate_evaluator_result(self.valid_data)
        self.assertIn("Missing required field: item_id", str(context.exception))

    def test_approval_status_other_than_not_approval_is_invalid(self):
        self.valid_data["approval_status"] = "approved"
        with self.assertRaises(EvaluatorResultValidationError) as context:
            validate_evaluator_result(self.valid_data)
        self.assertIn("appears to claim approval authority", str(context.exception))
        
        self.valid_data["approval_status"] = "rejected"
        with self.assertRaises(EvaluatorResultValidationError) as context:
            validate_evaluator_result(self.valid_data)
        self.assertIn("appears to claim approval authority", str(context.exception))

    def test_target_invocation_other_than_not_invoked_is_invalid(self):
        self.valid_data["target_invocation"] = "invoked"
        with self.assertRaises(EvaluatorResultValidationError) as context:
            validate_evaluator_result(self.valid_data)
        self.assertIn("appears to claim execution capability", str(context.exception))

    def test_decision_claiming_approval_is_invalid(self):
        for bad_decision in ["approve", "approved", "execute", "invoke"]:
            self.valid_data["decision"] = bad_decision
            with self.assertRaises(EvaluatorResultValidationError) as context:
                validate_evaluator_result(self.valid_data)
            self.assertIn("appears to claim approval authority", str(context.exception))

    def test_reasons_and_warnings_renderable_as_lists(self):
        self.valid_data["reasons"] = "Just a string"
        with self.assertRaises(EvaluatorResultValidationError) as context:
            validate_evaluator_result(self.valid_data)
        self.assertIn("must be a list", str(context.exception))
        
        self.valid_data["reasons"] = ["A reason"]
        self.valid_data["warnings"] = "Just a string warning"
        with self.assertRaises(EvaluatorResultValidationError) as context:
            validate_evaluator_result(self.valid_data)
        self.assertIn("must be a list", str(context.exception))

if __name__ == '__main__':
    unittest.main()
