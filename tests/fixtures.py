"""Scripted provider for exercising the runner without the network."""

import json


def tool(turn, name, args):
    return {"stop_reason": "tool_use", "content": [
        {"type": "tool_use", "id": f"tool-{turn}", "name": name, "input": args}
    ]}


def last_tool_content(messages):
    return json.loads(messages[-1]["content"][0]["content"])


class ScriptedProvider:
    mode = "offline_fixture"
    model = "scripted-not-a-model"

    def __init__(self):
        self.step = 0

    def send(self, *, system, messages, tools, timeout):
        self.step += 1
        if self.step == 1:
            return tool(1, "search_evidence", {"query": "identity lookup contract"})
        if self.step == 2:
            hits = last_tool_content(messages)["matches"]
            return tool(2, "read_excerpt", {"source_id": hits[0]["source_id"]})
        if self.step == 3:
            excerpt = last_tool_content(messages)
            assert "exact email match" in excerpt["text"]
            return tool(3, "search_evidence", {"query": "organization directory visibility policy implementation query"})
        if self.step == 4:
            return tool(4, "read_excerpt", {"source_id": "POL-01"})
        if self.step == 5:
            return tool(5, "read_excerpt", {"source_id": "IMP-01"})
        missing = "error" in last_tool_content(messages)
        report = {"summary": "Separate identity matching from directory visibility.",
                  "findings": [
                      {"requirement_id": "REQ-01", "component": "Directory",
                       "claim": "Directory-query enforcement is unverified from the supplied case."
                       if missing else "The current directory query filters by active organization.",
                       "claim_type": "implementation", "status": "unverified" if missing else "supported",
                       "citations": [] if missing else [{
                           "source_id": "IMP-01",
                           "quote": "filters associations by the caller's active organization ID"}]},
                  ],
                  "open_decisions": ["How should concurrent association requests be handled?"]}
        return {"stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps(report)}]}
