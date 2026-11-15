# EPHESUS — Google AI Studio agent demo

This prototype tests whether an agent can distinguish what a policy requires
from what the implementation evidence supports. The case uses fictional data.

## Investigation question

Does the current directory query limit results to the caller's active
organization when assessing REQ-01, reuse of an existing professional identity?

## Reproduce the two runs

1. Open Antigravity Agent Preview in Google AI Studio and select Gemini 3.8 Flash.
2. Paste [system-instructions.md](system-instructions.md) into Run settings → System instructions.
3. In a fresh session and environment, mount these files as inline sources:

   | Repo file | Destination in AI Studio |
   |---|---|
   | [AGENTS.md](.agents/AGENTS.md) | `/workspace/.agents/AGENTS.md` |
   | [POL-01.md](evidence/POL-01.md) | `/workspace/evidence/POL-01.md` |
   | [IMP-01.md](evidence/IMP-01.md) | `/workspace/evidence/IMP-01.md` |

4. Keep Filesystem tools enabled. Turn off Code execution, Grounding with Google Search, and URL context.
5. Send the exact text from [prompt.md](prompt.md). Do not paste the evidence into the chat.
6. Start a second fresh session and environment. Keep the model, instructions, tool settings, and prompt the same. Mount only AGENTS.md and POL-01.md. Omit IMP-01.md and rerun.
7. Compare the verdicts and expand the View File entries to verify which files the agent opened.

## Observed results

| Run | Evidence supplied | Verdict |
|---|---|---|
| [Run 1](results/run-01-supported.md) | Policy and implementation excerpt | **SUPPORTED** for this query, with an exact quote from IMP-01 |
| [Run 2](results/run-02-unverified.md) | Same policy, no implementation excerpt | **UNVERIFIED** because the policy alone does not show what the query does |

The policy stayed the same. Withholding the implementation excerpt changed
what the BA could verify. It did not show that the query fails to enforce
the rule. The next step is to request the query excerpt or a focused
organization-scoping test.

## Scope and capture limits

This folder documents a hosted AI Studio prototype. It does not contain a
local Antigravity runtime. The saved Run 1 response includes a citation but
no captured file-read trace. The saved Run 2 trace shows tool names but
not the expanded file paths. These two runs do not establish production
behavior, independent QUAESTOR review, or time savings.
