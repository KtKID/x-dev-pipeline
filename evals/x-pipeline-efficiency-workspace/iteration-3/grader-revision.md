# Grader revision before paired scoring

The first hidden pass on journal candidate run 1 exposed two evaluator assumptions absent from the public task:

1. The task fixes argument errors at exit code 2 and requires a JSON error object; it does not name the error code `USAGE`.
2. The task fixes sorted compact JSON and UTF-8 bytes; it does not choose `json.dumps(ensure_ascii=False)` over the default escaped representation.

The evaluator now accepts any non-empty structured argument error code at exit 2 and independently validates either canonical JSON Unicode representation, requiring the record bytes and CRC to use the same representation. Runtime behavior, field set, ordering, separators and CRC algorithm remain strict.

This correction happened before any baseline run and before the candidate saw grader output. The initial 90/100 file is preserved as `grading.pre-revision.json`; all paired scores use the revised frozen evaluator.

The first baseline grading then exposed a third representation-only assumption: the evaluator required every module in the spec to use its full `fixture/backend/*.py` path. The public task defines the module boundary by the four basenames, and the baseline spec contains all four in its impact-boundary table. The check now accepts those exact basenames anywhere in the validated spec. The baseline pre-correction result is preserved as `grading.pre-path-revision.json`; the substantive missing `unit`/`smoke`/`e2e` evidence labels remain a failure.
