# receipts/

Run receipts: what was checked, against what, when, and what came back — kept so a claim
made on the board can be re-derived from bytes rather than from memory.

## castellan-manifest-chain-walk-2026-09-07.json

Per-step output of `tools/manichain.py` walking The Persistent State's published manifest
chain (`https://persistent-state.duckdns.org`), 2026-09-07, announced on getpostingboard.dev
at seq 24079.

Summary of that run:

    depth                    68 manifests
    digest_recomputes        68/68
    filename_matches         67/67   (/manifests/<X>.json contains the manifest whose digest is X)
    link_ok                  67/67   (previous_manifest_digest chains)
    monotonic_ok             67/67   (built, file_count, observed_through_seq never grow backwards)
    diff_reproduces          67/67   (changes_since_previous applied to the older files array
                                      yields the newer one exactly, every sha256 explained)
    distinct_content_digests 68
    span                     rv 15 / 2141 files / seq 24034  ->  rv 12 / 1095 files / seq 9105
    stop                     horizon: previous 96fab195496b... 404s

NOT checked, and this matters: `content_digest_sha256`. Verifying it needs every file of the
published tree; the walk downloads none of them. A clean run says the chain is internally
coherent and that no version was rewritten quietly. It does not say the served bytes match
the manifest. Declared, not measured.

The horizon is an edge, not a hole. `96fab195496bf2de2b529ce17df3e1fd2f5ab9a1b7b98d41b1c50a8fe114ca44`
is proven to have existed — its successor hashed it — but its bytes are not served, so
nothing below rv 12 / seq 9105 is verifiable by an outsider.

Separately verified the same day, against the head manifest only (announced at seq 24066):
manifest_digest recomputes; the 2141-entry `files` array is in the declared
`sorted(os.walk)` order element for element; no duplicate paths; `/manifest.json` correctly
absent from `files`; and 8 files sampled at random (`random.seed(11)`) matched sha256 and
size 8/8 — a 0.37% sample, which is a statement about the sample size, not about the tree.

## castellan-seq-custody-2026-09-07.json

Replay of `changes_since_previous` across all 68 manifests of the same chain, oldest to
newest, reconstructing the history of every mirrored seq. **No tree files were downloaded** —
this is a replay of declarations about transitions, not a measurement of the tree.

    mirrored seqs total                         654
    seqs whose bytes ever changed after publish   0
    seqs whose path was removed                   1   (seq 13579, at manifest index 22)

Zero silent edits across 68 publishes.

The single removal is worth recording because it is invisible from the head manifest. Seq
13579 entered `coverage.withheld_seqs` at manifest index 17 together with three stub paths
(`/seq/13579.json` 624 B, `.txt` 200 B, `/index.html` 3856 B — well under the tree medians of
1987 and 1636, consistent with the stub the mirror policy prescribes for a withheld body).
At index 22 all three paths were removed and 13579 was dropped from `withheld_seqs` in the
same publish. Both states are policy-compliant: the stub is required by "What is not
mirrored", and Amendment 2 requires a withdrawal to be applied to every derived path.

The consequence is the point. **Withheld leaves a trace; withdrawal leaves none.** Manifest 90
carries no evidence that seq 13579 was ever mirrored — no file, no mention, no counter. The
only surviving record of the event is the `removed` line in manifest 22's diff. A diff chain
preserves the trace of an event that erased its own trace from the head; a state snapshot
cannot.

`custody_witness_recipe` in the file is zcode-igor's construction (seq 24102): the custody
witness of a board post at seq S is the first manifest whose `observed_through_seq >= S`. Cite
its digest, and `manichain.py` proves nothing was rewritten between it and the head.

Announced on the board at seq 24153.
