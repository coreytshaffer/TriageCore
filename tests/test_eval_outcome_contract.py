import os
import json
import tempfile
import unittest
from pathlib import Path

from triage_core.eval_outcome_contract import (
    build_actual_outcome,
    write_actual_outcome,
    write_actual_outcomes,
    project_privacy_report_to_actual_outcome
)
from triage_core.privacy_scanner import PrivacyReport

class TestEvalOutcomeContract(unittest.TestCase):
    def test_build_valid_outcome(self):
        outcome = build_actual_outcome(
            case_id="privacy_leak_attempt_001",
            decision="block",
            boundary_family="privacy",
            reasons=["persistent_artifact_contains_sensitive_content"],
            audit_required=True,
            human_approval_required=False
        )
        self.assertEqual(outcome["case_id"], "privacy_leak_attempt_001")
        self.assertEqual(outcome["decision"], "block")
        self.assertEqual(outcome["boundary_family"], "privacy")
        self.assertEqual(outcome["reasons"], ["persistent_artifact_contains_sensitive_content"])
        self.assertTrue(outcome["audit_required"])
        self.assertFalse(outcome["human_approval_required"])
        self.assertNotIn("diagnostic_details", outcome)

    def test_build_valid_outcome_with_diagnostic_details(self):
        outcome = build_actual_outcome(
            case_id="privacy_leak_attempt_002",
            decision="block",
            boundary_family="privacy",
            reasons=["persistent_artifact_contains_sensitive_content"],
            audit_required=True,
            human_approval_required=False,
            diagnostic_details=["Scanner matched something raw"]
        )
        self.assertEqual(outcome["case_id"], "privacy_leak_attempt_002")
        self.assertEqual(outcome["diagnostic_details"], ["Scanner matched something raw"])

    def test_missing_or_invalid_fields(self):
        with self.assertRaises(ValueError):
            build_actual_outcome(
                case_id="", # Empty string
                decision="block",
                boundary_family="privacy",
                reasons=[],
                audit_required=True,
                human_approval_required=False
            )
            
        with self.assertRaises(ValueError):
            build_actual_outcome(
                case_id="test_001",
                decision=None, # Invalid type
                boundary_family="privacy",
                reasons=[],
                audit_required=True,
                human_approval_required=False
            )
            
        with self.assertRaises(ValueError):
            build_actual_outcome(
                case_id="test_001",
                decision="block",
                boundary_family="privacy",
                reasons="not_a_list", # String instead of list
                audit_required=True,
                human_approval_required=False
            )

        with self.assertRaises(ValueError):
            build_actual_outcome(
                case_id="test_001",
                decision="block",
                boundary_family="privacy",
                reasons=[123], # Non-string in reasons
                audit_required=True,
                human_approval_required=False
            )

        with self.assertRaises(ValueError):
            build_actual_outcome(
                case_id="test_001",
                decision="block",
                boundary_family="privacy",
                reasons=[],
                audit_required=True,
                human_approval_required=False,
                diagnostic_details="not_a_list"
            )

        with self.assertRaises(ValueError):
            build_actual_outcome(
                case_id="test_001",
                decision="block",
                boundary_family="privacy",
                reasons=[],
                audit_required=True,
                human_approval_required=False,
                diagnostic_details=[123]
            )

    def test_path_unsafe_case_id(self):
        with self.assertRaises(ValueError):
            build_actual_outcome(
                case_id="../etc/passwd",
                decision="block",
                boundary_family="privacy",
                reasons=[],
                audit_required=True,
                human_approval_required=False
            )

    def test_write_actual_outcome(self):
        outcome = build_actual_outcome(
            case_id="write_test_001",
            decision="allow",
            boundary_family="none",
            reasons=[],
            audit_required=False,
            human_approval_required=False
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = write_actual_outcome(outcome, tmpdir)
            self.assertTrue(file_path.exists())
            self.assertEqual(file_path.name, "write_test_001.json")
            
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertEqual(data["case_id"], "write_test_001")

    def test_write_multiple_outcomes(self):
        outcomes = [
            build_actual_outcome(
                case_id="test_mult_001",
                decision="allow",
                boundary_family="none",
                reasons=[],
                audit_required=False,
                human_approval_required=False
            ),
            build_actual_outcome(
                case_id="test_mult_002",
                decision="block",
                boundary_family="privacy",
                reasons=["leak"],
                audit_required=True,
                human_approval_required=False
            )
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = write_actual_outcomes(outcomes, tmpdir)
            self.assertEqual(len(paths), 2)
            self.assertTrue((Path(tmpdir) / "test_mult_001.json").exists())
            self.assertTrue((Path(tmpdir) / "test_mult_002.json").exists())

    def test_duplicate_case_id(self):
        outcomes = [
            build_actual_outcome(
                case_id="dup_001",
                decision="allow",
                boundary_family="none",
                reasons=[],
                audit_required=False,
                human_approval_required=False
            ),
            build_actual_outcome(
                case_id="dup_001",
                decision="block",
                boundary_family="privacy",
                reasons=["leak"],
                audit_required=True,
                human_approval_required=False
            )
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                write_actual_outcomes(outcomes, tmpdir)

class TestPrivacyReportProjection(unittest.TestCase):
    def test_project_passed_report(self):
        report = PrivacyReport(passed=True, violations=[], detections=["Some detection"])
        outcome = project_privacy_report_to_actual_outcome(
            case_id="test_pass_001",
            report=report
        )
        self.assertEqual(outcome["decision"], "allow")
        self.assertEqual(outcome["boundary_family"], "privacy")
        self.assertEqual(outcome["reasons"], [])
        self.assertFalse(outcome["audit_required"])
        self.assertNotIn("diagnostic_details", outcome)

    def test_project_failed_report(self):
        report = PrivacyReport(
            passed=False,
            violations=["Unknown violation A", "Unknown violation B"],
            detections=[]
        )
        outcome = project_privacy_report_to_actual_outcome(
            case_id="test_fail_001",
            report=report
        )
        self.assertEqual(outcome["decision"], "block")
        self.assertEqual(outcome["boundary_family"], "privacy")
        self.assertEqual(outcome["reasons"], ["privacy_check_failed"])
        self.assertTrue(outcome["audit_required"])
        self.assertEqual(outcome["diagnostic_details"], ["Unknown violation A", "Unknown violation B"])

    def test_project_failed_report_with_ssn_pattern(self):
        report = PrivacyReport(
            passed=False,
            violations=["Detected possible SSN pattern in packet content; metadata contains_pii=False."],
            detections=[]
        )
        outcome = project_privacy_report_to_actual_outcome(
            case_id="test_fail_002",
            report=report
        )
        self.assertEqual(outcome["decision"], "block")
        self.assertEqual(outcome["reasons"], ["metadata_privacy_conflict", "ssn_pattern_detected"])
        self.assertEqual(outcome["diagnostic_details"], ["Detected possible SSN pattern in packet content; metadata contains_pii=False."])

    def test_project_failed_report_deduplicates_and_sorts(self):
        report = PrivacyReport(
            passed=False,
            violations=[
                "Detected possible SSN pattern in packet content; metadata contains_pii=False.",
                "Detected possible SSN pattern in packet content; metadata contains_pii=False.",
                "Unknown violation A"
            ],
            detections=[]
        )
        outcome = project_privacy_report_to_actual_outcome(
            case_id="test_fail_003",
            report=report
        )
        self.assertEqual(outcome["decision"], "block")
        self.assertEqual(outcome["reasons"], ["metadata_privacy_conflict", "privacy_check_failed", "ssn_pattern_detected"])
        self.assertEqual(outcome["diagnostic_details"], [
            "Detected possible SSN pattern in packet content; metadata contains_pii=False.",
            "Detected possible SSN pattern in packet content; metadata contains_pii=False.",
            "Unknown violation A"
        ])

if __name__ == '__main__':
    unittest.main()
