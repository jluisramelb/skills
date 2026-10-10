import json
import tempfile
import unittest
from pathlib import Path

from scripts.aggregate_benchmark import generate_benchmark, generate_markdown
from scripts.run_step_eval import plan_jobs, run_job
from tests.fixtures import make_skill, scripted_executor


def _grading(pass_rate):
    return {"summary": {"pass_rate": pass_rate, "passed": int(pass_rate * 2), "failed": 2 - int(pass_rate * 2), "total": 2},
            "expectations": []}


class AggregateStepsTests(unittest.TestCase):
    """Builds a small workspace with two models and checks the step summary.

    - "good" always returns the golden artifacts.
    - "drifty" extracts the wrong topic in runs 1 and 2 (critical failure that
      spreads into write/count) and writes a different sentence every run.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        skill = make_skill(root)
        cls.ws = root / "ws" / "iteration-1"
        executor = scripted_executor({
            "drifty": {
                "01-extract.json": ['{"topic": "beavers"}', '{"topic": "beavers"}', '{"topic": "otters"}', '{"topic": "otters"}'],
                "03-write.md": ["Beavers build dams.", "Beavers chew wood all day.", "Otters float.",
                                "Otters hold hands while they sleep and also juggle small pebbles for fun."],
            },
        })
        for job in plan_jobs(skill, cls.ws, ["good", "drifty"], 4, None, ["write"], None, 60):
            run_job(job, executor)
        cls.benchmark = generate_benchmark(cls.ws, "tiny-skill")
        cls.summary = cls.benchmark["step_summary"]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_layout_and_metadata(self):
        self.assertEqual(self.summary["configs"], ["drifty", "good"])
        self.assertEqual([s["id"] for s in self.summary["steps"]], ["extract", "approve", "write", "count"])
        self.assertEqual(self.summary["steps"][2]["inputs"], ["extract", "approve"])
        self.assertEqual(self.benchmark["metadata"]["runs_per_configuration"], 4)
        # The whole-run summary still works with models as configurations
        self.assertIn("good", self.benchmark["run_summary"])

    def test_good_model_is_stable(self):
        cell = self.summary["cells"]["write"]["good"]
        self.assertEqual(cell["pass_rate"]["mean"], 1.0)
        self.assertEqual(cell["consistency"]["exact_match_rate"], 1.0)
        self.assertEqual(cell["consistency"]["mean_divergence"], 0.0)
        self.assertEqual(cell["flags"], [])

    def test_extract_consistency_and_field_agreement(self):
        cons = self.summary["cells"]["extract"]["drifty"]["consistency"]
        self.assertEqual(cons["kind"], "json")
        self.assertEqual(cons["exact_match_rate"], 0.5)
        self.assertEqual(cons["field_agreement"], {"topic": 0.5})
        reasons = {f["reason"] for f in self.summary["cells"]["extract"]["drifty"]["flags"]}
        self.assertIn("unstable_output", reasons)
        self.assertIn("inconsistent", reasons)
        self.assertEqual(self.summary["cells"]["extract"]["drifty"]["success_rate"], 0.5)
        self.assertEqual(self.summary["cells"]["extract"]["good"]["success_rate"], 1.0)

    def test_failure_attribution_uses_isolated_runs(self):
        fa = self.summary["cells"]["write"]["drifty"]["failure_attribution"]
        # Runs 1-2 fail because extract failed; run 4 is too long (own failure)
        self.assertEqual(fa["chain_failure_rate"], 0.75)
        self.assertEqual(fa["source"], "isolated")
        # The fake executor ignores its inputs, so it writes the same (bad)
        # sentences even from golden inputs: isolation shows those failures
        # are the step's own, and nothing is left to blame on upstream.
        iso = self.summary["cells"]["write"]["drifty"]["isolated"]
        self.assertEqual(iso["runs"], 4)
        self.assertEqual(iso["failure_rate"], 0.75)
        self.assertEqual(fa["own_failure_rate"], 0.75)
        self.assertEqual(fa["inherited_failure_rate"], 0.0)

    def test_contamination_attribution_without_isolation(self):
        fa = self.summary["cells"]["count"]["drifty"]["failure_attribution"]
        self.assertEqual(fa["source"], "contamination")
        self.assertEqual(fa["inherited_failure_rate"], 0.5)
        self.assertGreaterEqual(fa["chain_failure_rate"], 0.5)

    def test_propagation_and_model_gap(self):
        edges = {(p["from"], p["to"], p["config"]): p for p in self.summary["propagation"]}
        e = edges[("extract", "write", "drifty")]
        self.assertEqual((e["upstream_critical_failures"], e["downstream_failures"], e["rate"]), (2, 2, 1.0))
        self.assertNotIn(("extract", "write", "good"), edges)
        gaps = [f for f in self.summary["flags"] if f["reason"] == "model_gap"]
        self.assertTrue(any(f["step"] == "extract" for f in gaps))

    def test_markdown_has_step_section(self):
        md = generate_markdown(self.benchmark)
        self.assertIn("## Step Breakdown", md)
        self.assertIn("extract → write", md)
        self.assertIn("model_gap", md)


class AggregateBackwardCompatTests(unittest.TestCase):
    def test_no_step_summary_for_classic_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            for config, rate in (("with_skill", 1.0), ("without_skill", 0.5)):
                for r in (1, 2):
                    run = ws / "eval-0" / config / f"run-{r}"
                    run.mkdir(parents=True)
                    (run / "grading.json").write_text(json.dumps(_grading(rate)))
            benchmark = generate_benchmark(ws, "x")
            self.assertNotIn("step_summary", benchmark)
            self.assertEqual(benchmark["run_summary"]["delta"]["pass_rate"], "+0.50")
            self.assertEqual(benchmark["metadata"]["runs_per_configuration"], 2)
            self.assertNotIn("Step Breakdown", generate_markdown(benchmark))


if __name__ == "__main__":
    unittest.main()
