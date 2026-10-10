import json
import tempfile
import unittest
from pathlib import Path

from scripts.quick_validate import validate_skill
from scripts.step_manifest import downstream, topological_order, upstream, validate_manifest, validate_skill_steps
from tests.fixtures import evals, make_skill, manifest

REPO_SKILLS = Path(__file__).resolve().parents[2]


class StepManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self, m=None, e=None):
        skill = make_skill(self.root, m, e)
        return validate_manifest(json.loads((skill / "evals" / "steps.json").read_text()), skill,
                                 json.loads((skill / "evals" / "evals.json").read_text()))

    def test_valid_manifest(self):
        self.assertEqual(self.errors(), [])

    def test_graph_helpers(self):
        steps = manifest()["steps"]
        self.assertEqual(topological_order(steps), ["extract", "approve", "write", "count"])
        self.assertEqual(upstream(steps, "count"), {"write", "extract", "approve"})
        self.assertEqual(downstream(steps, "approve"), {"write", "count"})

    def test_cycle_detected(self):
        m = manifest()
        m["steps"][0]["inputs"] = ["count"]
        errs = self.errors(m)
        self.assertTrue(any("cycle" in e for e in errs), errs)

    def test_missing_type_and_bad_output(self):
        m = manifest()
        del m["steps"][0]["type"]
        m["steps"][2]["output"] = "write.md"
        errs = self.errors(m)
        self.assertTrue(any("'type'" in e for e in errs), errs)
        self.assertTrue(any("<NN>-write" in e for e in errs), errs)

    def test_unknown_input(self):
        m = manifest()
        m["steps"][2]["inputs"] = ["nope"]
        self.assertTrue(any("unknown input step 'nope'" in e for e in self.errors(m)))

    def test_deterministic_needs_command(self):
        m = manifest()
        del m["steps"][3]["command"]
        self.assertTrue(any("'command'" in e for e in self.errors(m)))

    def test_command_placeholder_must_be_an_input(self):
        m = manifest()
        m["steps"][3]["command"] = ["python", "x.py", "{input:extract}", "{output}"]
        self.assertTrue(any("{input:extract}" in e for e in self.errors(m)))

    def test_human_step_needs_recorded_decision(self):
        e = evals()
        e["evals"][0].pop("golden_dir")
        e["evals"][0]["step_assertions"]["count"] = []
        errs = self.errors(None, e)
        self.assertTrue(any("no recorded decision" in x for x in errs), errs)

        # A manifest-level fixture fixes it
        m = manifest()
        m["steps"][1]["fixture"] = "evals/files/golden/otters/02-approve.json"
        self.tmp.cleanup()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.assertEqual(self.errors(m, e), [])

    def test_bad_assertions(self):
        e = evals()
        sa = e["evals"][0]["step_assertions"]
        sa["write"].append({"text": "x", "kind": "vibes"})
        sa["write"].append({"text": "x", "kind": "programmatic", "check": {"type": "reference_similarity"}})
        sa["write"].append({"text": "x", "kind": "llm"})
        sa["ghost"] = []
        errs = self.errors(None, e)
        self.assertTrue(any("'kind'" in x for x in errs), errs)
        self.assertTrue(any("not a valid programmatic check" in x for x in errs), errs)
        self.assertTrue(any("'rubric'" in x for x in errs), errs)
        self.assertTrue(any("unknown step 'ghost'" in x for x in errs), errs)

    def test_quick_validate_reports_manifest_errors(self):
        m = manifest()
        m["steps"][0]["inputs"] = ["count"]
        skill = make_skill(self.root, m)
        ok, message = validate_skill(skill)
        self.assertFalse(ok)
        self.assertIn("cycle", message)

    def test_skill_without_manifest_is_unchanged(self):
        skill = make_skill(self.root)
        (skill / "evals" / "steps.json").unlink()
        self.assertEqual(validate_skill_steps(skill), [])
        self.assertEqual(validate_skill(skill), (True, "Skill is valid!"))

    def test_internal_comms_pilot_manifest_is_valid(self):
        self.assertEqual(validate_skill_steps(REPO_SKILLS / "internal-comms"), [])


if __name__ == "__main__":
    unittest.main()
