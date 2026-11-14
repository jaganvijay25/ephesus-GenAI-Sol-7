from copy import deepcopy
from io import BytesIO
import json
import unittest
from urllib.error import HTTPError

from ephesus.contracts import InvalidReport, validate_report
from ephesus.evidence import CASES, load_case, search
from ephesus.provider import ClaudeProvider, ProviderError
from ephesus.runner import investigate
from tests.fixtures import ScriptedProvider, last_tool_content, tool


class FixedProvider:
    mode = "test"
    model = "test"

    def __init__(self, *replies):
        self.replies = iter(replies)

    def send(self, **kwargs):
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply


def final(report):
    return {"stop_reason": "end_turn", "content": [
        {"type": "text", "text": json.dumps(report)}]}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.case = load_case(CASES[0])

    def test_scripted_protocol_and_evidence_gap(self):
        complete = investigate(self.case, ScriptedProvider())
        variant = investigate(load_case(CASES[1]), ScriptedProvider())
        self.assertEqual(complete["status"], variant["status"])
        self.assertEqual(complete["status"], "completed")
        self.assertEqual(complete["mode"], "offline_fixture")
        self.assertNotEqual(complete["case_version"], variant["case_version"])
        self.assertEqual(complete["report"]["findings"][0]["status"], "supported")
        self.assertEqual(variant["report"]["findings"][0]["status"], "unverified")
        self.assertEqual(variant["tool_trace"][-1]["status"], "not_found")
        self.assertNotIn("IMP-01", [s["source_id"] for s in variant["read_sources"]])

    def test_case_scope_and_search(self):
        with self.assertRaises(ValueError):
            load_case("../README.md")
        self.assertEqual(search(self.case, "identity lookup contract")[0]["source_id"], "API-01")
        self.assertNotIn("text", search(self.case, "directory")[0])

    def test_prompt_starts_with_index_not_source_contents(self):
        class InspectProvider(ScriptedProvider):
            def send(self, **kwargs):
                if self.step == 0:
                    payload = json.loads(kwargs["messages"][0]["content"])
                    assert set(payload) == {"requirement", "evidence_index", "tool_budget"}
                    assert all(set(s) == {"source_id", "title", "kind"}
                               for s in payload["evidence_index"])
                return super().send(**kwargs)

        self.assertEqual(investigate(self.case, InspectProvider())["status"], "completed")

    def test_tool_allowlist_rejects_path_and_unknown_tool(self):
        class InspectProvider(FixedProvider):
            def send(self, **kwargs):
                if len(kwargs["messages"]) > 1:
                    assert "error" in last_tool_content(kwargs["messages"])
                return super().send(**kwargs)

        p = InspectProvider(
            tool(1, "read_excerpt", {"source_id": "../../README.md"}),
            tool(2, "shell", {"command": "irrelevant"}),
            ProviderError("Test stop"),
        )
        run = investigate(self.case, p)
        self.assertEqual([e["status"] for e in run["tool_trace"]],
                         ["not_found", "invalid_request"])
        self.assertEqual(run["read_sources"], [])

    def test_citations_are_checked(self):
        report = investigate(self.case, ScriptedProvider())["report"]
        bad = deepcopy(report)
        bad["findings"][0]["citations"][0]["quote"] = "made-up quote"
        with self.assertRaisesRegex(InvalidReport, "quote does not match"):
            validate_report(bad, self.case.evidence, {"IMP-01"})
        with self.assertRaisesRegex(InvalidReport, "not read"):
            validate_report(report, self.case.evidence, {"POL-01"})

    def test_policy_does_not_prove_implementation(self):
        report = investigate(self.case, ScriptedProvider())["report"]
        report["findings"][0]["citations"] = [{
            "source_id": "POL-01", "quote": "Directory visibility is restricted"}]
        with self.assertRaisesRegex(InvalidReport, "lacks evidence of its type"):
            validate_report(report, self.case.evidence, {"POL-01"})

    def test_provider_errors_do_not_become_success(self):
        run = investigate(self.case, FixedProvider(ProviderError("Claude returned HTTP 429")))
        self.assertEqual(run["status"], "incomplete")
        self.assertIsNone(run["report"])
        self.assertIn("429", run["error"])

    def test_budget_exhaustion_stops_extra_calls(self):
        p = FixedProvider(tool(1, "read_excerpt", {"source_id": "API-01"}),
                          tool(2, "read_excerpt", {"source_id": "IMP-01"}))
        run = investigate(self.case, p, max_tools=1)
        self.assertEqual(run["status"], "incomplete")
        self.assertEqual(len(run["tool_trace"]), 1)
        self.assertIn("budget", run["error"])

    def test_no_excerpts_means_no_completed_assessment(self):
        report = investigate(self.case, ScriptedProvider())["report"]
        run = investigate(self.case, FixedProvider(final(report)))
        self.assertIn("No case excerpts", run["error"])
        self.assertIsNone(run["report"])

    def test_invalid_json_and_provider_stop(self):
        for stop, value in (("end_turn", "not JSON"), ("max_tokens", "{}")):
            with self.subTest(stop=stop):
                p = FixedProvider(tool(1, "read_excerpt", {"source_id": "API-01"}), {
                    "stop_reason": stop, "content": [{"type": "text", "text": value}]})
                self.assertEqual(investigate(self.case, p)["status"], "incomplete")

    def test_timeout_after_provider_call(self):
        ticks = iter([0, 0, 91, 91])
        run = investigate(self.case, FixedProvider(final({})), clock=lambda: next(ticks))
        self.assertIn("deadline", run["error"])


class ProviderTests(unittest.TestCase):
    def test_constructs_expected_messages_request(self):
        def opener(req, timeout):
            self.assertEqual(req.full_url, "https://api.anthropic.com/v1/messages")
            self.assertEqual(req.get_header("Anthropic-version"), "2023-06-01")
            self.assertEqual(timeout, 8)
            payload = json.loads(req.data)
            self.assertEqual(payload["model"], "fixture-model")
            self.assertEqual(payload["output_config"]["format"]["type"], "json_schema")
            self.assertEqual(payload["tools"], [{"name": "test"}])
            self.assertNotIn("placeholder-key", req.data.decode())
            return BytesIO(b'{"type":"message","stop_reason":"end_turn"}')

        reply = ClaudeProvider("placeholder-key", "fixture-model", opener).send(
            system="test", messages=[], tools=[{"name": "test"}], timeout=8)
        self.assertEqual(reply["stop_reason"], "end_turn")

    def test_transport_errors_are_sanitized(self):
        def opener(req, timeout):
            raise HTTPError(req.full_url, 401, "must not be echoed", {}, None)

        with self.assertRaisesRegex(ProviderError, "^Claude returned HTTP 401$"):
            ClaudeProvider("placeholder-key", "fixture-model", opener).send(
                system="test", messages=[], tools=[], timeout=1)


if __name__ == "__main__":
    unittest.main()
