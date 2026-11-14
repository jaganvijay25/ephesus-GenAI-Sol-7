"""Bounded tool loop. Model requests are proposals, never direct I/O."""

from datetime import datetime, timezone
import json
from time import monotonic
from uuid import uuid4

from .contracts import (
    InvalidReport, PROMPT_VERSION, REPORT_VERSION, SYSTEM_PROMPT, TOOLS, validate_report,
)
from .evidence import Case, search
from .provider import ProviderError


def _lookup(case, block, read_ids):
    name = block.get("name")
    args = block.get("input")
    event = {"tool": name if name in ("search_evidence", "read_excerpt") else "unknown",
             "status": "ok", "source_ids": []}
    field = {"search_evidence": "query", "read_excerpt": "source_id"}.get(event["tool"])
    if (not field or not isinstance(args, dict) or set(args) != {field}
            or not isinstance(args[field], str) or not 1 <= len(args[field].strip()) <= 160):
        event["status"] = "invalid_request"
        return {"error": "Unknown tool or invalid argument"}, event
    if name == "search_evidence":
        hits = search(case, args[field])
        event["source_ids"] = [hit["source_id"] for hit in hits]
        return {"matches": hits}, event
    item = case.evidence.get(args[field])
    if item is None:
        event["status"] = "not_found"
        return {"error": "Source ID is not available in this case"}, event
    read_ids.add(item.source_id)
    event["source_ids"] = [item.source_id]
    return {"source_id": item.source_id, "kind": item.kind, "text": item.text}, event


def investigate(case: Case, provider, *, max_tools=6, timeout=90, clock=monotonic):
    if not 1 <= max_tools <= 20 or not 1 <= timeout <= 300:
        raise ValueError("Tool and time budgets are outside supported limits")
    started = clock()
    result = {
        "run_id": uuid4().hex,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "case_id": case.case_id,
        "case_version": case.version,
        "mode": provider.mode,
        "requested_model": provider.model,
        "prompt_version": PROMPT_VERSION,
        "report_version": REPORT_VERSION,
        "status": "incomplete",
        "model_calls": [],
        "tool_trace": [],
        "read_sources": [],
        "report": None,
    }
    read_ids = set()
    messages = [{"role": "user", "content": json.dumps({
        "requirement": case.requirement,
        "evidence_index": case.index(),
        "tool_budget": max_tools,
    })}]
    try:
        for _ in range(max_tools + 1):
            remaining = timeout - (clock() - started)
            if remaining <= 0:
                raise ProviderError("Run deadline reached")
            tool_turn = len(result["tool_trace"]) < max_tools
            reply = provider.send(system=SYSTEM_PROMPT, messages=messages,
                                  tools=TOOLS if tool_turn else [], timeout=remaining)
            if clock() - started >= timeout:
                raise ProviderError("Run deadline reached")
            usage = reply.get("usage")
            stop = reply.get("stop_reason")
            result["model_calls"].append({
                "model": reply.get("model") if isinstance(reply.get("model"), str) else None,
                "stop_reason": stop if isinstance(stop, str) else None,
                "usage": {k: usage[k] for k in (
                    "input_tokens", "output_tokens", "cache_creation_input_tokens",
                    "cache_read_input_tokens") if type(usage.get(k)) is int}
                if isinstance(usage, dict) else {},
            })
            blocks = reply.get("content")
            if not isinstance(blocks, list) or not all(isinstance(b, dict) for b in blocks):
                raise ProviderError("Provider returned invalid content blocks")
            if stop == "tool_use":
                calls = [b for b in blocks if b.get("type") == "tool_use"]
                ids = [b.get("id") for b in calls]
                if not calls or not all(isinstance(i, str) and i for i in ids) or len(set(ids)) != len(ids):
                    raise ProviderError("Provider returned invalid tool call IDs")
                if len(calls) + len(result["tool_trace"]) > max_tools:
                    raise ProviderError("Tool call budget exceeded")
                replies = []
                for call in calls:
                    value, event = _lookup(case, call, read_ids)
                    result["tool_trace"].append(event)
                    replies.append({"type": "tool_result", "tool_use_id": call["id"],
                                    "is_error": "error" in value, "content": json.dumps(value)})
                messages.extend([{"role": "assistant", "content": blocks},
                                 {"role": "user", "content": replies}])
                continue
            if stop != "end_turn":
                raise ProviderError("Provider did not return a complete assessment")
            if any(b.get("type") == "tool_use" for b in blocks):
                raise ProviderError("Provider returned unexpected tool calls on its final turn")
            parts = [b["text"] for b in blocks if b.get("type") == "text"
                     and isinstance(b.get("text"), str)]
            try:
                report = json.loads("".join(parts))
            except ValueError:
                raise InvalidReport("Assessment was not valid JSON") from None
            if not read_ids:
                raise InvalidReport("No case excerpts were read during the investigation")
            validate_report(report, case.evidence, read_ids)
            result.update(status="completed", report=report)
            break
        else:
            raise ProviderError("Model turn budget exceeded")
    except (ProviderError, InvalidReport) as exc:
        result["error"] = str(exc)
    result["read_sources"] = [case.evidence[sid].__dict__ for sid in sorted(read_ids)]
    result["elapsed_ms"] = round((clock() - started) * 1000)
    return result
