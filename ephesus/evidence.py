"""Read-only lookup over a fixed registry of fictional artifacts."""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping

CASE_ROOT = Path(__file__).resolve().parent.parent / "cases" / "professional-identity"
CASES = ("professional-identity", "professional-identity-missing-excerpt")


@dataclass(frozen=True)
class Evidence:
    source_id: str
    title: str
    kind: str
    text: str


@dataclass(frozen=True)
class Case:
    case_id: str
    version: str
    requirement: str
    evidence: Mapping[str, Evidence]

    def index(self):
        return [{"source_id": s.source_id, "title": s.title, "kind": s.kind}
                for s in self.evidence.values()]


def load_case(case_id: str) -> Case:
    if case_id not in CASES:
        raise ValueError("Unknown case ID")
    requirement = (CASE_ROOT / "requirement.md").read_text(encoding="utf-8")
    contract = json.loads((CASE_ROOT / "contract.json").read_text(encoding="utf-8"))
    op = contract["paths"]["/fictional/professionals/lookup"]["get"]
    params = ", ".join(f'{p["name"]} ({p["schema"]["type"]}, required={str(p["required"]).lower()})'
                       for p in op["parameters"])
    sources = {
        "API-01": Evidence("API-01", "Identity lookup contract", "contract",
                           f"GET /fictional/professionals/lookup\n{op['description']}\nParameters: {params}"),
        "POL-01": Evidence("POL-01", "Organization visibility policy", "policy",
                           (CASE_ROOT / "visibility-policy.md").read_text(encoding="utf-8").strip()),
    }
    if case_id == CASES[0]:
        sources["IMP-01"] = Evidence(
            "IMP-01", "Directory query implementation excerpt", "implementation",
            (CASE_ROOT / "visibility-implementation.txt").read_text(encoding="utf-8").strip())
    raw = json.dumps([case_id, requirement, [s.__dict__ for s in sources.values()]],
                     ensure_ascii=False, sort_keys=True).encode("utf-8")
    return Case(case_id, sha256(raw).hexdigest()[:16], requirement, MappingProxyType(sources))


def search(case: Case, query: str) -> list[dict]:
    words = set(re.findall(r"[a-z0-9]+", query.lower()))
    scored = []
    for s in case.evidence.values():
        hay = set(re.findall(r"[a-z0-9]+", f"{s.title} {s.kind} {s.text}".lower()))
        if score := len(words & hay):
            scored.append((score, s))
    scored.sort(key=lambda pair: (-pair[0], pair[1].source_id))
    return [{"source_id": s.source_id, "title": s.title, "kind": s.kind}
            for _, s in scored[:4]]
