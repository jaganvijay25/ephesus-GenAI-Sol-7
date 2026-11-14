"""Local demo UI for the standalone EPHESUS investigation runner."""

import json
import os

import streamlit as st

from ephesus.evidence import CASES, load_case
from ephesus.provider import ClaudeProvider
from ephesus.runner import investigate
from tests.fixtures import ScriptedProvider


def render_run(record):
    if record["mode"] == "offline_fixture":
        st.caption("Scripted result • no live AI inference")
    else:
        st.caption(f"Live Claude • requested model: {record['requested_model']}")
    if record["status"] != "completed":
        st.error(f"Run incomplete. {record.get('error', 'No validated report was returned.')}")
    else:
        report = record["report"]
        st.write(report["summary"])
        for finding in report["findings"]:
            st.markdown(f"**{finding['status'].upper()}** · {finding['claim_type']} · {finding['requirement_id']}")
            st.write(finding["claim"])
            for citation in finding["citations"]:
                st.caption(f"Source {citation['source_id']}")
                st.code(citation["quote"], language="text")
        if report["open_decisions"]:
            st.markdown("**Open decisions for the reviewer**")
            for decision in report["open_decisions"]:
                st.write(decision)
    with st.expander("Investigation trace and exact excerpts read"):
        st.caption(f"Run {record['run_id']} · Case fingerprint {record['case_version']}")
        for n, event in enumerate(record["tool_trace"], 1):
            ids = ", ".join(event["source_ids"]) or "—"
            st.text(f"{n}. {event['tool']} · {event['status']} · {ids}")
        if not record["read_sources"]:
            st.caption("No case excerpts were read.")
        for source in record["read_sources"]:
            st.markdown(f"**{source['source_id']} · {source['title']}**")
            st.code(source["text"], language="text")
    st.download_button(
        "Download run record", json.dumps(record, indent=2, ensure_ascii=False),
        file_name=f"{record['case_id']}-{record['run_id']}.json",
        mime="application/json", key=f"download-{record['run_id']}",
    )


def main():
    st.set_page_config(page_title="EPHESUS Unified", layout="wide")
    st.title("EPHESUS Unified")
    st.subheader("Evidence-grounded technical impact analysis")
    st.write("Compare one fictional change request with and without implementation evidence. "
             "The policy stays the same. The claim about current enforcement may change.")

    with st.sidebar:
        st.header("Run configuration")
        mode = st.radio("Mode", ("Scripted walkthrough", "Live Claude"), key="run_mode")
        model = st.text_input("Claude API model ID",
                              value=os.environ.get("EPHESUS_MODEL") or "claude-sonnet-4-6",
                              disabled=mode != "Live Claude", key="model_id").strip()
        if mode == "Live Claude":
            st.caption("Live runs send only the bundled fictional inputs to Anthropic and use API credits.")

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip() if mode == "Live Claude" else ""
    live = mode == "Live Claude"
    ready = not live or bool(key and model)
    if not live:
        st.info("Scripted walkthrough — no live AI inference. These results are not benchmark measurements.")
    elif not ready:
        st.warning("Live Claude requires ANTHROPIC_API_KEY in the PowerShell window that launches "
                   "Streamlit and a valid model ID. No scripted fallback will be used.")

    case_a, case_b = map(load_case, CASES)
    with st.expander("Read the fictional requirement", expanded=True):
        st.markdown(case_a.requirement)
    st.caption("Citation checks verify that a quote exists in a source read during the run. "
               "A human still checks whether the quote supports the claim.")

    context = (mode, model if live else "")
    if st.session_state.get("result_context") != context:
        st.session_state["runs"] = {}
        st.session_state["result_context"] = context

    columns = st.columns(2)
    for column, case, heading, button in zip(
        columns, (case_a, case_b),
        ("Implementation excerpt included", "Implementation excerpt withheld"),
        ("Run with implementation evidence", "Run without implementation evidence"),
    ):
        with column:
            st.markdown(f"### {heading}")
            st.caption("Available evidence: " + ", ".join(case.evidence))
            if st.button(button, key=f"run-{case.case_id}", disabled=not ready):
                with st.spinner("Running EPHESUS…"):
                    provider = ClaudeProvider(key, model) if live else ScriptedProvider()
                    st.session_state["runs"][case.case_id] = investigate(case, provider)
            record = st.session_state["runs"].get(case.case_id)
            if record:
                render_run(record)
            else:
                st.caption("Run this case to see its assessment and evidence trail.")


if __name__ == "__main__":
    main()
