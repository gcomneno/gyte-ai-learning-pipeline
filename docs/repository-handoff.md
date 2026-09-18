# Approval-gated repository handoff

GYTE can automate a validated public candidate into a downstream consumer repository up to pull-request creation. The workflow deliberately separates **preview/approval** from **repository mutation**.

## Authority rule

```text
validated public candidate
  -> prepare handoff / preview (no consumer-repo mutation)
  -> explicit publication approval bound to exact plan_id
  -> branch + materialize + validate + commit + push + PR
  -> merge remains downstream authority
```

No remote write occurs during `prepare`.

## Prepare phase

`prepare` requires:

- a current validated `public_candidate` stage;
- matching consumer contract;
- configured consumer checkout (contract `local_checkout` or explicit `--checkout`);
- clean consumer checkout;
- checkout currently on the declared base branch.

It records the exact:

- consumer repository/base branch;
- checkout path and current base HEAD;
- candidate path/SHA-256;
- consumer contract path/SHA-256;
- target relative path;
- deterministic feature branch;
- validation commands;
- `plan_id` derived from those immutable inputs.

It writes only private GYTE handoff artifacts:

- `repository-handoff/<consumer>/plan.json`;
- `repository-handoff/<consumer>/preview.diff`.

The consumer repository is not modified.

```bash
PYTHONPATH=src python bin/gyte-repository-handoff prepare \
  /path/to/private/workspace \
  consumer-contracts/physics-study.json \
  --checkout /path/to/physics-study
```

## Explicit approval/apply phase

After reviewing the preview, the exact `plan_id` is the approval token:

```bash
PYTHONPATH=src python bin/gyte-repository-handoff apply \
  /path/to/private/workspace/repository-handoff/physics-study/plan.json \
  --approve handoff-<exact-plan-hash>
```

Before any mutation, apply rechecks candidate bytes, contract bytes, clean checkout, base branch and base HEAD. Any drift requires a new prepare/approval cycle.

After approval it performs, in order:

1. create the feature branch;
2. materialize only the declared target file;
3. rerun the private/public boundary scan;
4. run `git diff --check`;
5. run each configured `validation_commands` entry;
6. `git add` only the declared target;
7. commit;
8. push the feature branch;
9. create a pull request with `gh pr create`.

Validation therefore happens before commit/push. Merge is never performed by this operation.

## Consumer validation

A contract may declare commands as argv arrays, for example:

```json
{
  "validation_commands": [
    ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
  ]
}
```

Commands run with the consumer checkout as working directory. They are not executed during preview because the candidate has not yet been materialized there.

## Failure and retry semantics

`result.json` records the exact failed step and progress flags (`branch_created`, `materialized`, `validated`, `committed`, `pushed`, `pr_created`) plus the base HEAD, candidate identity and branch needed for diagnosis/retry.

Before a remote push, failures attempt to restore the original target and return the checkout to the original base HEAD/branch. After a push, the failure record intentionally preserves the pushed-branch fact rather than pretending rollback occurred remotely.

A retry must use the recorded state deliberately; silent duplicate pushes or automatic merges are outside this contract.

## Boundaries

The handoff operation does not:

- accept unreviewed/private GYTE artifacts;
- write to a consumer repository before explicit approval;
- broaden the allowed consumer target beyond the contract;
- skip configured validation;
- merge the pull request;
- grant the generated artifact authority over downstream review policy.
