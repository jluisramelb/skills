import json
import tempfile
import unittest
from pathlib import Path

from scripts.grade_steps import grade_run, run_check
from scripts.run_step_eval import extract_artifact, plan_jobs, run_job
from tests.fixtures import make_skill, scripted_executor


class RunCheckTests(unittest.TestCase):
    def test_programmatic_checks(self):
        data = {"a": {"b": [1, 2, 3]}, "name": "Mobile"}
        text = json.dumps(data)
        cases = [
            ({"type": "json_valid"}, True),
            ({"type": "json_required", "fields": ["a.b", "name"]}, True),
            ({"type": "json_required", "fields": ["a.c"]}, False),
            ({"type": "json_field_equals", "field": "name", "value": "mobile", "case_insensitive": True}, True),
            ({"type": "json_field_equals", "field": "a.b.1", "value": 2}, True),
            ({"type": "json_array_length", "field": "a.b", "min": 1, "max": 2}, False),
            ({"type": "contains", "field": "a", "value": "3"}, True),
            ({"type": "not_contains", "value": "mobile"}, False),
            ({"type": "regex", "pattern": "^Mob", "field": "name"}, True),
            ({"type": "regex", "pattern": "xyz", "should_match": False}, True),
        ]
        for check, expected in cases:
            with self.subTest(check=check):
                passed, evidence = run_check(check, text, data, Path("."))
                self.assertEqual(passed, expected, evidence)

    def test_text_checks_and_invalid_json(self):
        text = "Progress: a\nPlans: b\n\nProblems: c\n"
        self.assertTrue(run_check({"type": "line_count", "min": 3, "max": 3}, text, None, Path("."))[0])
        self.assertFalse(run_check({"type": "word_count", "max": 3}, text, None, Path("."))[0])
        passed, evidence = run_check({"type": "json_required", "fields": ["x"]}, "nope", None, Path("."))
        self.assertFalse(passed)
        self.assertIn("not valid JSON", evidence)

    def test_extract_artifact(self):
        self.assertEqual(extract_artifact("hi <artifact>\n```json\n{\"a\":1}\n```\n</artifact>", "json"), '{\n  "a": 1\n}\n')
        self.assertEqual(extract_artifact("<artifact>line</artifact>", "markdown"), "line\n")
        self.assertIsNone(extract_artifact("no tags", "markdown"))


class RunAndGradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_chain(self, skill, executor, model="m", run_number=1, cache=True):
        jobs = plan_jobs(skill, self.root / "ws", [model], run_number, None, [], None, 60, use_cache=cache)
        job = [j for j in jobs if j["run_number"] == run_number and j["mode"] == "chain"][0]
        run_job(job, executor)
        return Path(job["run_dir"])

    def test_chain_run_all_steps_pass(self):
        skill = make_skill(self.root)
        run_dir = self.run_chain(skill, scripted_executor({}))
        grading = json.loads((run_dir / "grading.json").read_text())
        self.assertEqual(sorted(p.name for p in (run_dir / "outputs" / "steps").iterdir()),
                         ["01-extract.json", "02-approve.json", "03-write.md", "04-count.json"])
        self.assertEqual(grading["summary"]["failed"], 0)
        write = grading["steps"]["write"]
        self.assertEqual(write["pending"], 1)  # llm check left pending without a grader
        self.assertIsNone(write["failure_origin"])
        self.assertTrue((run_dir / "logs" / "02-approve.json").exists())
        self.assertIn("replayed_fixture", json.loads((run_dir / "logs" / "02-approve.json").read_text()))
        timing = json.loads((run_dir / "timing.json").read_text())
        self.assertEqual(timing["total_tokens"], 20)

    def test_critical_failure_contaminates_downstream(self):
        skill = make_skill(self.root)
        executor = scripted_executor({"m": {"01-extract.json": '{"topic": "beavers"}',
                                            "03-write.md": "Beavers build dams."}})
        run_dir = self.run_chain(skill, executor)
        steps = json.loads((run_dir / "grading.json").read_text())["steps"]
        self.assertTrue(steps["extract"]["critical_failed"])
        self.assertEqual(steps["extract"]["failure_origin"], "own")
        self.assertTrue(steps["write"]["contaminated"])
        self.assertEqual(steps["write"]["contaminated_by"], ["extract"])
        self.assertEqual(steps["write"]["failure_origin"], "inherited")
        self.assertEqual(steps["count"]["failure_origin"], "inherited")  # 3 words != golden 6

    def test_missing_artifact_skips_downstream(self):
        skill = make_skill(self.root)

        def broken(prompt, model, cwd, skill_path, timeout):
            return {"text": "I could not do it", "duration_ms": 0, "tokens": 0, "is_error": False}

        run_dir = self.run_chain(skill, broken)
        steps = json.loads((run_dir / "grading.json").read_text())["steps"]
        self.assertFalse(steps["extract"]["exists"])
        self.assertTrue(steps["extract"]["critical_failed"])
        self.assertTrue(steps["write"]["contaminated"])
        log = json.loads((run_dir / "logs" / "02-approve.json").read_text())
        self.assertTrue(log["skipped"])

    def test_llm_grader_is_used(self):
        skill = make_skill(self.root)
        run_dir = self.run_chain(skill, scripted_executor({}))
        grading = grade_run(run_dir, None, lambda rubric, text, ctx: (False, "not delightful"))
        fun = [a for a in grading["steps"]["write"]["assertions"] if a["id"] == "fun"][0]
        self.assertEqual((fun["passed"], fun["evidence"]), (False, "not delightful"))
        self.assertEqual(grading["steps"]["write"]["failure_origin"], "own")

    def test_manual_llm_verdicts_survive_regrading(self):
        skill = make_skill(self.root)
        run_dir = self.run_chain(skill, scripted_executor({}))
        grading = json.loads((run_dir / "grading.json").read_text())
        for a in grading["steps"]["write"]["assertions"]:
            if a["id"] == "fun":
                a["passed"], a["evidence"] = True, "made me smile"
        (run_dir / "grading.json").write_text(json.dumps(grading))
        regraded = grade_run(run_dir)
        self.assertEqual(regraded["steps"]["write"]["pending"], 0)
        self.assertIn({"text": "[write] Is fun", "passed": True, "evidence": "made me smile"}, regraded["expectations"])

    def test_deterministic_step_cached(self):
        skill = make_skill(self.root)
        first = self.run_chain(skill, scripted_executor({}), run_number=1)
        second = self.run_chain(skill, scripted_executor({}), run_number=2)
        log1 = json.loads((first / "logs" / "04-count.json").read_text())
        log2 = json.loads((second / "logs" / "04-count.json").read_text())
        self.assertFalse(log1["cached"])
        self.assertTrue(log2["cached"])
        self.assertEqual((first / "outputs/steps/04-count.json").read_text(),
                         (second / "outputs/steps/04-count.json").read_text())
        self.assertFalse((first / "outputs/steps/04-count.json.repeat").exists())

    def test_nondeterministic_step_flagged(self):
        skill = make_skill(self.root, random_script=True)
        run_dir = self.run_chain(skill, scripted_executor({}))
        steps = json.loads((run_dir / "grading.json").read_text())["steps"]
        ids = {a["id"]: a["passed"] for a in steps["count"]["assertions"]}
        self.assertIs(ids["auto-reproducible"], False)
        self.assertEqual(list((self.root / "ws" / ".step-cache").glob("*")), [])

    def test_isolated_run_uses_golden_inputs(self):
        skill = make_skill(self.root)
        jobs = plan_jobs(skill, self.root / "ws", ["m"], 1, None, ["write"], "old_skill", 60)
        iso = [j for j in jobs if j["mode"] == "isolated"][0]
        self.assertTrue(iso["run_dir"].endswith("m__old_skill/isolated/write/run-1"))
        executor = scripted_executor({"m": {"01-extract.json": '{"topic": "beavers"}'}})
        run_job(iso, executor)
        run_dir = Path(iso["run_dir"])
        steps_dir = run_dir / "outputs" / "steps"
        self.assertEqual(json.loads((steps_dir / "01-extract.json").read_text()), {"topic": "otters"})
        self.assertFalse((steps_dir / "04-count.json").exists())
        grading = json.loads((run_dir / "grading.json").read_text())
        self.assertEqual(list(grading["steps"]), ["write"])
        self.assertEqual(grading["steps"]["write"]["inputs_source"], "golden")
        self.assertFalse(grading["steps"]["write"]["contaminated"])


if __name__ == "__main__":
    unittest.main()
