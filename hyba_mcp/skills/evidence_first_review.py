"""Evidence-first review procedure for HYBA engineering agents."""

SKILL_ID = "review.evidence_first"
TITLE = "Apply the mandatory evidence-first technical review procedure"
SOURCE = "EUCLID engineering review procedure, required by AGENTS.md"
INPUT_SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "mandatory_for_technical_reviews": {"type": "boolean"},
        "procedure": {"type": "string"},
    },
    "required": ["mandatory_for_technical_reviews", "procedure"],
    "additionalProperties": False,
}
COST_ESTIMATE = 1
RISK_LEVEL = 0.0
TIME_ESTIMATE = 0.1

PROCEDURE = """# Evidence-First Technical Review

## Establish the review basis

1. Inspect the actual repository before drawing architectural conclusions. Identify the repository, target branch or release, reviewed commit SHA, and any local changes that affect the evidence. When reviewing a deployment, identify its artifact digest or build ID, environment, and relationship to the reviewed source. Use the available repository and operational records. State concrete access gaps and continue with the evidence available.
2. Read the current architecture authority register or owner-approved decisions, relevant contracts, and release criteria. Trace actual entry points through configuration, dispatch, subsystem handoffs, and externally visible outcomes. Use wiring and call sites to establish what executes by default or under an explicit flag. Treat observed implementation and declared ownership as separate findings. If they diverge, cite both and record the discrepancy for the owner. Resolve current HYBA ownership from the authoritative sources for this review.
3. Keep audit work read-only with respect to project code, architecture, and live configuration unless the user authorises changes. Run relevant non-mutating checks where feasible. For authorised documentation edits, preserve declared boundaries and describe actual behavior, conditions, and evidence. Apply any implementation changes only within the authorised scope.

## Verify each claim at the applicable level

| Claim | Evidence to inspect |
| --- | --- |
| Implemented | Source at a pinned revision and reachable call path, including required configuration and relevant failure behavior. |
| Tested | Actual result for the relevant revision or artifact. Capture suite or command, environment, outcome, and what the fixtures exercised. Distinguish authored tests from tests run, local runs from CI, and partial checks from full suites. |
| Merged | Target-branch history or merged PR and confirmation that the intended change is present at the reviewed head. |
| Runtime observed | Trace, logs, receipt, or measurement for the actual exercised path. Match the timestamp, environment, build, inputs, and observed outcome to the claim. |
| Deployed | Deployment record identifying the target environment and running artifact. Verify reachability or health independently when claimed. |
| Production qualified | Applicable owner-approved gates and required sign-off for the exact release or artifact. Record each required gate and its evidence. If criteria or evidence are missing, report that qualification is unverified. |

Evaluate each level independently. Check the provenance, revision, environment, and scope of inherited results before applying them to the target. State what a result demonstrates at the granularity requested, including whether evidence was directly checked or supplied by another party.

Require real runtime evidence for every live claim. Use synthetic inputs, mocks, replay, and loopback results only for the behavior they actually exercise, and label them explicitly. Never substitute simulated evidence for measured evidence or fill gaps with invented values. For HYBA mining, pool connection, authorisation, job receipt, search execution, share submission, and pool acceptance each require evidence for that specific event. For a hardware acceleration claim, verify execution on the named backend and device. A device listing or successful software hash result establishes only the event it records. Scope performance observations to their workload, measurement window, environment, and baseline where applicable.

## Report the decision and its evidence

- Give the disposition for the requested scope and revision, followed by material findings. For qualification or multiple claims, use a compact table with claim or gate, status, evidence reference, and gap. Cite commit-pinned files, PRs, test runs, deployment records, or timestamped telemetry close to each finding.
- Use **Unavailable** for an inaccessible source or missing measurement. Use **Unverified** when a claim lacks adequate supporting evidence. For checks, use **Not run** when no execution took place and **Blocked** when a specific prerequisite prevented execution. Reserve **Failed** for observed failures and **Pass** for criteria actually met. Include the reason alongside each open status.
- Separate observed facts, inferences, and reported assertions in the wording. Carry the same evidence limits into documentation, release notes, and summaries. For every material gap, identify the smallest concrete verification that would settle it."""

LIMITATIONS = (
    "The procedure requires agents to verify the underlying evidence.",
    "Retrieving the procedure does not establish that a review was performed.",
)


def run() -> dict[str, object]:
    """Return the required procedure without accessing external systems."""
    return {"mandatory_for_technical_reviews": True, "procedure": PROCEDURE}


EXAMPLES = ({"input": {}, "output": run()},)
