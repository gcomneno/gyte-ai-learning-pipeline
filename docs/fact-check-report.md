# Private fact-check report

GYTE can generate a private structured fact-check report from the current editorial candidate, or from prepared analysis when no current candidate exists.

Canonical boundary:

```text
fact-check report != source evidence
fact-check report != reviewed source lesson
fact-check completion != editorial approval
```

## Claim extraction

The base implementation identifies conservative prose sentences that are plausible fact-check candidates. Extraction identifies **what should be checked**; it does not decide truth.

Each claim receives a deterministic ID from its exact text and a priority (`high` or `medium`). Numeric or absolute-language claims are prioritized more strongly.

## Resolution states

Every claim records one of:

- `supported`;
- `unsupported`;
- `disputed`;
- `unresolved`.

A generated report defaults to `unresolved` with no references. This keeps missing verification visible instead of silently passing it.

Any status other than `unresolved` requires at least one explicit reference. References are evidence supplied to the fact-check operation; the generator does not invent them.

## Evidence file

Optional manual/external verification can be supplied as JSON:

```json
{
  "schema_version": 1,
  "claims": {
    "claim-0123456789abcdef": {
      "status": "supported",
      "references": [
        "https://example.org/authoritative-source"
      ],
      "editorial_qualification": "Supported only for the declared configuration."
    }
  }
}
```

Unknown/unresolved claims remain visible in the output.

## Output

The private workspace receives `fact-check-report.json` with:

- exact input filename, SHA-256 and byte count;
- extracted claims and deterministic IDs;
- priority;
- support status;
- supporting references;
- editorial qualification;
- aggregate unresolved count;
- explicit authority boundary fields showing that no review/publication authority was granted.

The operation records `stages.fact_check` only as `authority: fact-check-advisory`. It does not create or complete `stages.review`.

## Commands

Generate an unresolved report:

```bash
PYTHONPATH=src python bin/gyte-fact-check /path/to/private/workspace
```

Apply verified evidence:

```bash
PYTHONPATH=src python bin/gyte-fact-check \
  /path/to/private/workspace \
  --evidence /path/to/evidence.json
```

## Editorial use

A reviewer should inspect unresolved/disputed/unsupported claims before granting a reviewed-source checkpoint. The report can recommend qualifications, but it does not mutate the candidate/prepared analysis automatically and it does not certify absolute correctness.
