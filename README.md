# EPHESUS Unified · standalone AI architecture POC

A runnable, CLI-first **adaptation** of EPHESUS for technical change-impact assessments. It does not run or modify the original PRIÈNE/Claude Code agent. The illustrative case and every source in this repo are fictional.

## Open the Streamlit demo on Windows

Open PowerShell in the folder containing this README, then run:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

Open the **Local URL** printed by Streamlit. Select **Scripted walkthrough**, then run both cases. The same runner and citation checks used by the CLI handle both runs. The scripted provider stands in for Claude, so this verifies the demonstration flow, not AI quality. Download either run record to inspect the report, tool calls and sources. Changing mode or model clears the displayed runs so the two columns do not mix modes.

For live mode, stop Streamlit with **Ctrl+C** and start it from a PowerShell window with the API key loaded. The key is read from the environment, never typed into the web app or written to a file.

```powershell
& {
    $key = Read-Host "Anthropic API key" -AsSecureString
    if ($key.Length -eq 0) { return }
    try {
        $env:ANTHROPIC_API_KEY = [System.Net.NetworkCredential]::new("", $key).Password.Trim()
        python -m streamlit run streamlit_app.py --server.address 127.0.0.1
    }
    finally {
        Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
    }
}
```

Select **Live Claude**, enter the model ID available on your account, and run either case. Live mode requires usable Anthropic API credits. Failed live runs are marked incomplete and never replaced with scripted results. Live inference was not verified in the development environment.

## Run from the command line on Windows

Extract the ZIP and open PowerShell in the folder containing this README. Use Python 3.10 or newer. The **CLI** does not require any package installation or virtual environment.

```powershell
python -m unittest discover -v
python -m tests.offline_demo
```

If Windows resolves `python` to the Store alias, use the installed executable directly:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m tests.offline_demo
```

The offline walkthrough runs a scripted provider through the same orchestration and validation code. It illustrates the result with the implementation excerpt present and removed. **It does not run a model or measure AI performance.**

### Run live with Claude

Set `ANTHROPIC_API_KEY` privately in your local environment and use the exact Claude model ID available on your Anthropic account. In PowerShell, you can enter a key without echoing it or placing it in command history:

```powershell
$env:ANTHROPIC_API_KEY = [System.Net.NetworkCredential]::new("", (Read-Host "Anthropic API key" -AsSecureString)).Password
$env:EPHESUS_MODEL = Read-Host "Exact Claude model ID"
python -m ephesus --output runs/with-excerpt.json
python -m ephesus --case professional-identity-missing-excerpt --output runs/without-excerpt.json
Remove-Item Env:ANTHROPIC_API_KEY
```

Live mode sends the fictional requirement and evidence selected by the workflow to the Anthropic Messages API. It uses the direct Anthropic API credential, not a Claude Code subscription login. Each invocation may use multiple billable calls. A refusal, provider failure, invalid citation, or incomplete response is reported explicitly. No canned report is substituted. Use new output filenames on reruns or omit `--output` to print JSON.

Inspect `tool_trace`, `read_sources`, and `report.findings`. For the excerpt-removal test, look for the **implementation** claim, not the policy claim. The policy can still be cited. The policy alone cannot verify current enforcement. The live model's choice of claims and tools may vary, so check the actual result before showing it to mentors.

## What is in the repo

| Path | Purpose |
|---|---|
| `ephesus/runner.py` | Bounded model → evidence tool → model loop |
| `ephesus/evidence.py` | Fixed case registry, keyword search and exact excerpt lookup |
| `ephesus/contracts.py` | Prompt, report schema and citation checks |
| `ephesus/provider.py` | Server-side Claude Messages adapter |
| `cases/` | Fictional requirement, OpenAPI JSON, policy and implementation excerpt |
| `streamlit_app.py` | Local two-case demo interface over the same investigation runner |
| `requirements.txt` | Optional Streamlit dependency for the UI |
| `tests/` | Offline protocol and provider-contract tests |
| `docs/architecture.md` | Architecture, trace format and verification limits |

The ZIP contains a local Git repository and one initial commit. Nothing was pushed remotely. QUAESTOR, benchmark execution, ROI claims, hosted UI, API hosting and public deployment are outside this first milestone.
