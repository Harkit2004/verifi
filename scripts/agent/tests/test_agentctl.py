import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agentctl as ac  # noqa: E402


def issue(number, labels=(), body="", title="Some task"):
    return {"number": number, "title": title, "labels": [{"name": n} for n in labels], "body": body}


def meta(phase, seq, deps="", risk="low", size="s"):
    return f"text\n<!-- verifi-agent\nphase: {phase}\nseq: {seq}\ndepends-on: {deps}\nrisk: {risk}\nsize: {size}\n-->\n"


class ParseMetaTest(unittest.TestCase):
    def test_parses_all_fields(self):
        m = ac.parse_meta(meta(1, 4, "#12, #13"))
        self.assertEqual((m["phase"], m["seq"], m["depends_on"], m["risk"], m["size"]), (1, 4, [12, 13], "low", "s"))
        self.assertTrue(m["has_block"])

    def test_missing_block_gives_sortable_defaults(self):
        m = ac.parse_meta("no block here")
        self.assertEqual((m["phase"], m["seq"], m["depends_on"], m["has_block"]), (99, 9999, [], False))

    def test_event_markers_are_not_metadata(self):
        self.assertFalse(ac.parse_meta("<!-- verifi-agent:handoff status=partial -->")["has_block"])


class SelectNextTest(unittest.TestCase):
    def test_orders_by_phase_then_seq(self):
        issues = [
            issue(5, ["agent:ready"], meta(1, 1)),
            issue(3, ["agent:ready"], meta(0, 2)),
            issue(4, ["agent:ready"], meta(0, 1)),
        ]
        chosen, _ = ac.select_next(issues)
        self.assertEqual(chosen["number"], 4)

    def test_open_dependency_blocks(self):
        issues = [issue(1, ["needs:human"], meta(0, 1)), issue(2, ["agent:ready"], meta(0, 2, "#1"))]
        chosen, skipped = ac.select_next(issues)
        self.assertIsNone(chosen)
        self.assertIn((2, "waiting on #1"), skipped)

    def test_closed_dependency_does_not_block(self):
        chosen, _ = ac.select_next([issue(2, ["agent:ready"], meta(0, 2, "#1"))])
        self.assertEqual(chosen["number"], 2)

    def test_excluding_labels_and_epics(self):
        issues = [
            issue(1, ["agent:ready", "agent:in-progress"], meta(0, 1)),
            issue(2, ["agent:ready", "type:epic"], meta(0, 1)),
            issue(3, ["agent:ready", "needs:human"], meta(0, 1)),
            issue(4, ["agent:ready"], meta(0, 9, size="l")),
            issue(5, [], meta(0, 1)),
        ]
        chosen, skipped = ac.select_next(issues)
        self.assertIsNone(chosen)
        self.assertEqual({n for n, _ in skipped}, {1, 3, 4, 5})


class PrEvaluationTest(unittest.TestCase):
    def pr(self, labels=("risk:low",), checks="SUCCESS", review="", mergeable="MERGEABLE", sha="abc"):
        rollup = [{"status": "COMPLETED", "conclusion": checks}] if checks else []
        return {"labels": [{"name": n} for n in labels], "statusCheckRollup": rollup, "reviewDecision": review, "mergeable": mergeable, "headRefOid": sha}

    def test_green_low_risk_merges(self):
        self.assertEqual(ac.evaluate_pr(self.pr(), attempts=0, last_resume_sha=None), "merge")

    def test_unknown_or_high_risk_needs_human(self):
        self.assertEqual(ac.evaluate_pr(self.pr(labels=()), attempts=0, last_resume_sha=None), "needs-human")
        self.assertEqual(ac.evaluate_pr(self.pr(labels=("risk:high",)), attempts=0, last_resume_sha=None), "needs-human")
        self.assertEqual(ac.evaluate_pr(self.pr(labels=("risk:high", "human:approved")), attempts=0, last_resume_sha=None), "merge")

    def test_never_merges_without_checks(self):
        self.assertEqual(ac.evaluate_pr(self.pr(checks=""), attempts=0, last_resume_sha=None), "wait")

    def test_failures_resume_then_escalate(self):
        self.assertEqual(ac.evaluate_pr(self.pr(checks="FAILURE"), attempts=2, last_resume_sha=None), "resume")
        self.assertEqual(ac.evaluate_pr(self.pr(checks="FAILURE"), attempts=3, last_resume_sha=None), "escalate")

    def test_addressed_review_waits_for_rereview(self):
        pr = self.pr(review="CHANGES_REQUESTED", sha="s1")
        self.assertEqual(ac.evaluate_pr(pr, attempts=1, last_resume_sha="s1"), "wait")
        self.assertEqual(ac.evaluate_pr(pr, attempts=1, last_resume_sha="s0"), "resume")

    def test_conflicts_resume(self):
        self.assertEqual(ac.evaluate_pr(self.pr(mergeable="CONFLICTING"), attempts=0, last_resume_sha=None), "resume")


class MarkerTest(unittest.TestCase):
    def test_counts_and_last_session(self):
        comments = [
            {"body": "<!-- verifi-agent:session-start attempt=1 -->"},
            {"body": "<!-- verifi-agent:session-end session=ses_A exit=0 outcome=no-pr -->"},
            {"body": "<!-- verifi-agent:session-start attempt=2 -->"},
            {"body": ac.render_handoff(status="partial", done="x", next_step="y", session="ses_B")},
        ]
        self.assertEqual(ac.count_markers(comments, "session-start"), 2)
        self.assertEqual(ac.last_session_id(comments), "ses_B")
        self.assertEqual(ac.last_marker(comments, "handoff")["status"], "partial")


class MiscTest(unittest.TestCase):
    def test_branch_roundtrip(self):
        branch = ac.branch_for(42, "Add JSON envelope: CLI!")
        self.assertEqual(branch, "agent/42-add-json-envelope-cli")
        self.assertEqual(ac.issue_number_from_branch(branch), 42)

    def test_similar_titles(self):
        self.assertTrue(ac.similar_titles("Flaky docker sandbox test on Windows", "flaky docker sandbox test windows"))
        self.assertFalse(ac.similar_titles("Flaky docker sandbox test", "Add markdown report renderer"))

    def test_definition_of_ready(self):
        body = meta(1, 1) + "## Tests to write first\n- t\n## Acceptance criteria\n- [ ] a\n## Verification\nrun\n"
        self.assertEqual(ac.definition_of_ready(issue(1, ["risk:low"], body)), [])
        problems = ac.definition_of_ready(issue(1, [], "nothing"))
        self.assertTrue(any("risk" in p for p in problems))
        self.assertTrue(any("Acceptance" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
