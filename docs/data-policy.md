# PEMDS Data & Copyright Policy

**Status:** binding for implementation (operationalises specification section 6)
**Scope:** all code, data files, UI text, tooltips and generated reports

ASME, API, TEMA, HI, MSS, NACE and similar standards are copyrighted. PEMDS must
never reproduce their normative text, tables, figures or appendices. This policy
states how the product stays compliant while remaining useful.

## 1. Rules

1. **Cite, don't reproduce.** Store and display clause/paragraph numbers, symbol
   names and short paraphrases only. Never ship standard text, tables, figures or
   appendices verbatim in the repository, UI, tooltips or PDF reports.
2. **Formulas are code.** Implement the underlying engineering formulas from
   scratch in Python with a `{standard, edition, clause}` citation attached. No
   ASME/API/TEMA/HI/MSS names or logos beyond factual citation.
3. **Numeric data gets provenance, not wholesale copying.** Transcribe only the
   values needed; every data file carries a header
   `{source, edition, clause, licence, transcribed_on, checked_by}`. Prefer
   public-domain equivalents; where a table is large and central, make it a
   user-supplied data file rather than bundling the standard's table.
4. **Reports quote references, not clauses.** A report row shows
   `ASME VIII-1 (2023), UG-27(c)(1)` plus our own substitution — never clause prose.
5. **Benchmark numbers are facts; benchmark text is not.** Golden tests may
   compare numeric results against published examples; example text is not copied.
6. **Legal review before release** (risk R-2).

## 2. Data file format

Every JSON file under `src/pemds/data/` begins with a `provenance` header:

```json
{
  "provenance": {
    "source": "…",
    "edition": "…",
    "clause": "…",
    "licence": "…",
    "transcribed_on": "YYYY-MM-DD",
    "checked_by": "…",
    "source_tag": "S#"
  }
}
```

The loader (`pemds.data.loader`) rejects any file whose header is incomplete,
so a missing provenance block is a hard failure at load time.

## 3. Transcribed data workflow

1. Transcribe only the values actually used by a calculation.
2. Record the exact edition and clause in the file header.
3. Record `transcribed_on` (date) and `checked_by` (reviewer). Unreviewed data
   must be marked `UNVERIFIED` in `checked_by` and must not back a `verified`
   calculation.
4. If a value cannot be published safely, do not bundle it: expose the field as
   a user-supplied data file instead.

## 4. Enforcement

`scripts/citation_lint.py` runs in CI and fails when:

- a data file lacks a complete provenance header;
- a calculation returning a `Result` has no `@provable` clause/source metadata;
- a data file contains a string literal longer than 400 characters (suspected
  copied prose or table); or
- delivered source contains `TODO`/`FIXME` placeholder markers.

## 5. External-pressure charts (decision D4)

The UG-28 geometry and material charts are figures and are never reproduced.
`pemds.calc.external` implements the closed-form elastic relationship and marks
its result **experimental**; design outside the elastic range requires a
transcribed numeric chart dataset supplied by the user. See the module
docstring for the exact equations.
