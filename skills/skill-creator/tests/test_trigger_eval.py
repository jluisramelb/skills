import json
import tempfile
import unittest
from pathlib import Path

from scripts.trigger_eval import detect_trigger, evaluate, stage_skill
from scripts.utils import parse_skill_md
from tests.fixtures import make_skill


class TriggerEvalTests(unittest.TestCase):
    def test_detect_trigger_from_copilot_events(self):
        invoked = json.dumps({"type": "skill.invoked", "data": {"name": "tiny-skill-trigger-abc", "content": "..."}})
        tool = json.dumps({"type": "tool.execution_start",
                           "data": {"toolName": "skill", "arguments": {"skill": "tiny-skill-trigger-abc"}}})
        other = json.dumps({"type": "skill.invoked", "data": {"name": "some-other-skill"}})
        self.assertTrue(detect_trigger(["not json", invoked], "tiny-skill-trigger-abc"))
        self.assertTrue(detect_trigger([tool], "tiny-skill-trigger-abc"))
        self.assertFalse(detect_trigger([other, "[]", ""], "tiny-skill-trigger-abc"))

    def test_stage_skill_copies_under_unique_name_without_evals(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = make_skill(Path(tmp) / "src")
            project = Path(tmp) / "project"
            name = stage_skill(skill, project)
            staged = project / ".github" / "skills" / name
            self.assertTrue(name.startswith("tiny-skill-trigger-"))
            self.assertEqual(parse_skill_md(staged)[0], name)
            self.assertTrue((staged / "scripts" / "count_words.py").exists())
            self.assertFalse((staged / "evals").exists())

    def test_evaluate_scores_against_threshold(self):
        queries = [{"query": "make a skill", "should_trigger": True},
                   {"query": "weather", "should_trigger": False},
                   {"query": "flaky", "should_trigger": True}]
        hits = {"make a skill": [True, True], "weather": [False, False], "flaky": [True, False, False]}
        calls = {k: iter(v * 3) for k, v in hits.items()}
        report = evaluate(queries, 2, 0.5, lambda q: next(calls[q]))
        by_query = {r["query"]: r for r in report["results"]}
        self.assertEqual(by_query["make a skill"]["triggers"], 2)
        self.assertTrue(by_query["weather"]["pass"])
        self.assertEqual(report["summary"]["total"], 3)


if __name__ == "__main__":
    unittest.main()
