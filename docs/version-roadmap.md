# PEMDS — Version Roadmap & Release Plan

**Companion to:** `functional_requirment.md` (FR spec v0.4)
**Date:** 2026-10-06
**Defines:** what ships in v1.0, and how many releases to reach "complete"

---

## 0. Definition of "complete"

**v2.0 = all [M] + all [S] requirements shipped and verified.**

The [C] (could) items are an evergreen backlog by design — a code-compliance tool is never truly finished because ASME/API reissue editions every ~2 years. The realistic long-term goal is **v2.0 + yearly edition-maintenance releases (v2.x)**.

| Priority | Count meaning | In "complete"? |
|---|---|---|
| [M] must | v1 required | ✅ by v1.x |
| [S] should | v1.x depth | ✅ by v2.0 |
| [C] could | v2+ / on demand | ❌ evergreen backlog |

---

## 1. v1.0 — what should actually ship

**Principle:** v1.0 = working **core + verified thin slices in the highest-value packs**, everything else explicitly labelled *experimental*. An honest, smaller v1.0 beats a broad one where nothing is trustworthy — the GUI's **VAL-2 status indicator** ("verified vs experimental" per check) is what makes breadth safe.

| Area | In v1.0 (must) | Out of v1.0 (deferred) |
|---|---|---|
| **Platform** | Units (SI/imperial), project save/load, undo/redo, forms + sliders + live validation, GUI shell, provenance result objects, PDF report with formula trace, DXF GA drawing, simple 3D preview, golden-test harness | what-if comparison (IN-7), presets library (PM-5), workspace layouts (GUI-4) |
| **Data** | Starter materials set (~20–30 common steels with allowable stress vs temperature), **chemical component DB core (CC-1…CC-5, CC-10 — ~100 fluids)** | mixtures (CC-6), simulator import (CC-9), edition switcher (DB-7) |
| **ASME VIII-1 core** | UG-27 shell, UG-28/33 external, UG-32/34 heads, UG-36–41 openings, UG-98/99 MAWP & test, UW-11/12 joints | App. 2 bolted flanges (CORE-8), WRC local loads (CORE-9), fatigue (CORE-10), PWHT/MDMT (CORE-11) |
| **Packs — verified** | **PV** (full thin slice), **PU** (PU-1…PU-15), **FL** (B16.5 rating selection), **PS** (straight pipe + branch) | supports/anchors (PV-5), pump curves + affinity (PU-16/17), seal datasheet depth (PU-10) |
| **Packs — preview** | **TK / HX / CO** minimal: one governing thickness check each, flagged "experimental" in GUI and reports | API 650 wind/seismic (TK-4), TEMA tubesheets (HX-6), ASCE 7 column loads (CO-3) |

### v1.0 exit criteria (definition of done)

- [ ] All [M] items in the four verified packs pass golden tests (VAL-1)
- [ ] 100% of reported numbers carry `{standard, edition, clause}` provenance (CIT-1)
- [ ] No verbatim standard text anywhere in repo/UI/reports (CIT-2 lint passes)
- [ ] Report generation < 3 s; live recalc < 100 ms (NFR-1)
- [ ] TK/HX/CO visibly marked *experimental* everywhere they appear (VAL-2)
- [ ] Test coverage ≥ 90% on calculation modules (NFR-10)

---

## 2. Release roadmap

| Release | Scope | Depends on | Solo estimate |
|---|---|---|---|
| **v0.5** (alpha) | Platform + VIII-1 core + PV pack only, internal use | — | ~6–8 weeks |
| **v1.0** | Core complete; PV/PU/FL/PS **verified**; TK/HX/CO experimental; CC core; report + DXF + 3D | v0.5 | **+8–10 weeks (≈4–6 months total)** |
| **v1.1** | TK/HX/CO promoted to **verified**; materials set expanded; CC-6 mixtures, CC-8 service screening | v1.0 | +4–6 weeks |
| **v1.2** | **Depth:** PV-5 supports & anchors, CORE-8 App. 2 flanges, CO-3/TK-4 wind+seismic, PU-16/17 curve overlay + affinity laws, PU-10 seal datasheet | v1.1 | +6–8 weeks |
| **v1.3** | **Polish:** DR-6/7 drawing templates & relayout, 3D-3 section cuts, report appendix (RP-4), CC-7 user components | v1.2 | +4–6 weeks |
| **v2.0** ("complete") | EXT-3 CLI/API, PU-22 curve import, CC-9 simulator hand-off, 3D-5 clash detection, VAL-5 third-party validation campaign | v1.3 | +6–8 weeks |
| **v2.x** (ongoing) | Remaining [C] on demand (PU-21 PD pumps, CORE-10 fatigue, PU-23 pump banks…); yearly code-edition updates | v2.0 | ongoing |

### Totals

- **~5–6 releases** to reach "complete" (v2.0)
- **Solo: ~10–14 months**
- **Team of 2–3: ~5–7 months**

---

## 3. Effort reality notes

1. **Data entry & verification dominate (~40% of effort).** Writing UG-27 takes a day; building the allowable-stress table with provenance plus its golden tests takes longer. Verification — a human hand-checking every [M] calculation — is the long pole, not coding.
2. **"Complete" is a moving target.** ASME BPVC/API standards reissue on ~2-year cycles; every edition triggers a data-table review + regression run. This is why v2.x never stops and why DB-7 (edition switcher) matters.
3. **The main scope dial:** want a *sooner* credible v1.0 (~3 months)? Ship only **PV + PU + FL** as verified and move PS/TK/HX/CO entirely to v1.1. Every pack you promote to "verified" in v1.0 adds roughly 1–2 weeks of verification work.

---

## 4. Risk-to-release mapping

| Risk (FR §9) | Release that addresses it |
|---|---|
| R-1 Scope breadth | Breadth-first phasing; experimental labelling in v1.0 |
| R-2 Copyright | CIT-1/2 enforced from v0.5 (CI lint), legal review gate before v1.0 |
| R-3 Edition drift | DB-7 edition switcher in v1.1; v2.x annual updates |
| R-4 Engineering liability | VAL-2 status + report disclaimer in v0.5 |
| R-5 Pump data availability | Sample curves v1.0 → PU-22 import in v2.0 |
| R-7 Property-data accuracy | CC-10 provenance flags in v0.5 |

---

*Scope references use FR IDs from `functional_requirment.md` — cite them in issues (e.g. "v1.2: PU-17 affinity laws").*
