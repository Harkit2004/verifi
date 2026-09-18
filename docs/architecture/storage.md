# Run storage and tamper evidence

## Home

`VERIFI_HOME` (env or `--home`), default `~/.verifi`. Layout:

```
$VERIFI_HOME/
  runs/<run_id>/
  cache/images/          (Phase 1: image build metadata)
  packs/                 (Phase 2: installed attack packs)
```

## Run directory

```
runs/<run_id>/
  manifest.json          RunManifest (status updated during the run)
  spec.lock.json         LockedSpec (env refs unresolved; no secrets)
  events.jsonl           hash-chained Event log
  evidence/
    index.jsonl          one line per record: {id, kind, source, trusted, episode_id}
    objects/<id>.json    EvidenceRecord (canonical JSON)
  episodes/<episode_id>.json   EpisodeResult
  transcripts/<episode_id>.json  untrusted target transcript (human debugging only)
  findings.json          list[Finding] (sorted, canonical JSON)
  score.json             Score
  gate.json              GateResult
  report.json            Report
  report.md              rendered report
  verification.json      VerificationRecord, written LAST
```

Rules:

- All JSON written by verifi in the run directory uses `canonical_json` plus a trailing newline, and writes are atomic (write to `*.tmp`, then `os.replace`).
- Nothing in the run directory contains resolved secrets, host environment, or private attack payloads (INV-6: private cases are stored as `{id, sha256(payload)}` only).
- `run_id` format: `run_<UTC %Y%m%dT%H%M%SZ>_<8 hex>` (`RandomIds`); tests use `SequentialIds`.

## Event chain

```
event.hash = sha256_json({"seq": n, "ts": ..., "type": ..., "data": ..., "prev_hash": prev})
prev_hash of seq 1 = "0" * 64
```

Standard event types: `run.created`, `run.status`, `sandbox.created`, `sandbox.destroyed`, `episode.started`,
`episode.finished`, `evidence.recorded` (id + kind only), `detectors.finished`, `score.computed`, `report.written`.

## Verification id

`write_verification(run_dir)`:

1. Collect every regular file under the run dir except `verification.json`, as POSIX relative paths, sorted.
2. `files[path] = sha256_hex(file bytes)`.
3. `verification_id = "vfy_" + sha256_json(files)[:32]`.
4. Write `verification.json` = `{schema, verification_id, files}`.

`verify_run_dir(run_dir)` recomputes and reports: missing files, extra files, hash mismatches, a broken event chain
(`EventLog.verify`), and evidence objects whose id does not match their content. `verifi runs verify` exits 1 if any problem exists.

This is tamper *evidence*, not tamper *proof*: an attacker with write access can recompute everything.
Signing `verification.json` (e.g. Sigstore) is a later ADR.
