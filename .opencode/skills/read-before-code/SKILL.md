---
name: read-before-code
description: How to understand a verifi issue before writing code - read the issue sections, the referenced architecture docs, existing code and tests, and build a test-to-criterion plan. Load before touching any file.
---

# Read before code

## 1. Read the issue completely

`python scripts/agent/agentctl.py context <issue>`. Every task issue has these sections; note what each tells you:

| Section | Use |
|---|---|
| Context | why this exists; do not re-litigate it |
| Read first | docs you MUST open, in order |
| Tests to write first | exact test files and test names to create; this is your red list |
| Implementation notes | required module paths, names, signatures |
| Acceptance criteria | the only definition of done |
| Out of scope | things you must NOT do even if tempting |
| Verification | commands that must succeed at the end |

If a dependency listed in the metadata is still open, stop and release: `agentctl release <n> --to ready --reason "dependency #x open"`.

## 2. Read the referenced docs

Always skim `docs/architecture/overview.md` section "Layers" plus every doc in "Read first".
Contracts in `docs/architecture/interfaces.md` are **binding**: copy names and signatures exactly.

## 3. Read the code you will touch

```bash
git grep -n "<ClassOrFunctionName>" -- src tests
```

- Find the closest existing example of what you are building (another detector, another CLI operation, another tool) and imitate its structure, naming, and test style.
- Look at existing fixtures in `tests/conftest.py` and `tests/**/conftest.py` before writing new ones.

## 4. Write your plan (in your head / todo list, not a file)

```
AC1 "<criterion>"  -> tests/unit/.../test_x.py::test_a
AC2 "<criterion>"  -> tests/unit/.../test_x.py::test_b
files to create:   src/verifi/.../x.py
files to modify:   src/verifi/app/operations.py (register op)
not touching:      <things from Out of scope>
```

Every acceptance criterion needs at least one test. If a criterion cannot be tested, it is ambiguous: escalate.

## 5. Stop conditions

Escalate instead of starting if:

- the issue asks for a name or signature that contradicts `interfaces.md`,
- the "Read first" doc does not exist or does not cover what the issue assumes,
- the tests listed would require network access, real credentials, or a paid API.
