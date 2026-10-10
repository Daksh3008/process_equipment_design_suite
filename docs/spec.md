# PEMDS — Build Specification (v0.5 → v1.0)

**Project:** Process Equipment Mechanical Design Suite (working name "PEMDS")
**Document type:** Implementation specification — features, tasks, build approach, task acceptance
**Status:** Build spec v1.0 — derived from `functional_requirment.md` (FR spec v0.4) and `version-roadmap.md`
**Date:** 2026-10-06
**Runtime:** Python 3.12+
**GUI:** PySide6
**Scope of this document:** everything required to reach **v1.0**

---

## 0. How to read this document

- **§1–§7** are the shared context every task depends on: decisions, architecture, contracts, data policy, verification.
- **§8** is the complete **feature catalog** (every FR ID with priority and acceptance intent).
- **§9** is the **release plan** (v0.5, v1.0) with exit criteria.
- **§10** is the **task breakdown** — the core of this document. Every task states **What** (deliverable), **How** (exact build approach), **Done when** (acceptance), **FR** (traceability), and **Depends**.
- Task IDs: `P0-*` (foundations), `S5-*` (v0.5 sprints), `S10-*` (v1.0 sprints).
- Priority tags carried from the FR spec: **[M]** must (v1), **[S]** should (v1.x), **[C]** could (v2+). This document plans **[M]** to v1.0 and notes where **[S]** is pulled forward by the roadmap.

---

## 1. Product summary

PEMDS is a Python desktop application where a chemical/process engineer enters duty, geometry, loads, and material for process equipment via forms and sliders; the software executes code-based mechanical design calculations live and emits:

1. **Live pass/fail analysis** in the GUI.
2. **A calculation report (PDF)** with full formula trace and code-clause references.
3. **A 2D engineering drawing (DXF/PDF)** — GA style.
4. **A simple 3D preview** for geometry sanity-checking.

It is a lightweight, Python-native alternative to PV Elite / Compress / DesignCalcs, covering the pressure-containing and structural side of process equipment — **not** process simulation.

### 1.1 Equipment families (7)

| # | Family | Governing standard(s) |
|---|---|---|
| 1 | Pressure vessels | ASME BPVC VIII-1 (UG-27 shell, UG-28/33 external, UG-32/34 heads, UG-36–41 openings, UG-98/99 MAWP & test, UW-11/12 joints) |
| 2 | Storage tanks | API 650 / API 620 |
| 3 | Heat exchangers | ASME VIII-1 + TEMA (R/C/S), UHX reference |
| 4 | Flanges / nozzles | ASME B16.5 / B16.47, VIII-1 App. 2, B16.20 |
| 5 | Piping & supports | ASME B31.3 / B31.1, MSS SP-58, AISC |
| 6 | Columns / reactors | ASME VIII-1 + ASCE 7 wind/seismic, AISC/ACI |
| 7 | Pumps | API 610 / ISO 13709, API 682, ANSI/HI, ASME B73.1 / ISO 5199 / ISO 2858, NEMA MG-1, NACE MR0175 |

### 1.2 Primary users and use cases

| Persona | Need |
|---|---|
| Chemical engineer (primary) | Size/verify equipment from process data; produce a reviewable calc report; get a GA drawing |
| Reviewer / checker | Trace every number to inputs + code clause; see pass/fail and governing case |
| (later) CAD drafter | Import DXF output |
| (later) Automation | Headless CLI / Python API |

- **UC-1:** vessel duty → shell/head thickness, MAWP, nozzle reinforcement, hydrotest → PDF + DXF.
- **UC-2:** pump duty → selection, NPSH/power/motor checks, seal recommendation, nozzle-load check → API 610 datasheet + GA.
- **UC-3:** slide a parameter and watch pass/fail update live.
- **UC-4:** sweep a parameter family from CSV for many variants.

---

## 2. Locked decisions

These are settled and assumed by every task below.

| # | Decision | Value |
|---|---|---|
| D1 | **Code editions (default set)** | ASME VIII-1 + II-D **2023** (or 2025), B16.5/B16.47 **2020**, B31.3 **2022**, API 650 **13th**, API 620 **12th**, API 610 **11th**, API 682 **4th**, TEMA **10th**, ASCE **7-22**, AISC **360-22**, ACI **318-19**, NEMA **MG-1**, ISO 281 / 13709 / 5199 / 2858. All editions live in a registry (DB-7 adds more); every citation stores the edition at runtime. Use the edition you hold a licence for; confirm against the licensed copy during implementation. |
| D2 | **GUI framework** | **PySide6** (Qt6). Calculation engine stays GUI-agnostic. |
| D3 | **Drawing fidelity** | **GA-style parametric sketch** for v1.0 (dimension-driven relayout DR-7 is v1.3). |
| D4 | **External-pressure charts** | Publish **equations/curve-fits + transcribed numeric curve points with provenance**; never reproduce `ASME VIII-1` chart figures. |
| D5 | **Pump catalogue** | **Sample/generic curves only** in v1.0; vendor import (PU-22) is v2.0. |
| D6 | **Units workflow** | Internal **SI**; per-field display units; SI/imperial/mixed toggle. No separate imperial-first app. |
| D7 | **FR-CC backend** | **Hybrid**: CoolProp (MIT, pinned version) for property evaluation + our own NIST-sourced identity DB (CAS, synonyms, formula, MW). |
| D8 | **VAL-1 golden basis** | Public-domain worked examples (NIST/NASA/NRC/open OER) first, with a sign-off flag for any figure needing independent engineer verification. |

---

## 3. Architecture

### 3.1 Principles

1. **Core + packs.** Shared modules (units, materials DB, calculation engine, report engine, drawing engine, 3D preview, GUI shell) plus one plug-in pack per equipment family.
2. **Calculation = pure function.** `Calc(inputs, materials, code_version) -> Results` — no I/O, deterministic, unit-safe. GUI and reports are renderers of the same result object.
3. **Every number carries provenance** — see §5 Result object.
4. **Standards are data, not code — with provenance.** Coefficients/tables live in versioned data files keyed by edition, each with provenance metadata.
5. **Units internal SI, converted at the edge** with explicit display-unit control.
6. **Determinism** (NFR-2): pinned dependencies, float64, documented rounding only at display.

### 3.2 Repository layout

```
pemds/
├─ pyproject.toml
├─ src/pemds/
│  ├─ core/
│  │  ├─ units.py            # pint wrappers, SI internal, display conversion
│  │  ├─ provenance.py       # Citation, Provenance, VerificationStatus
│  │  ├─ result.py           # Result, ResultTree, Verdict, Issue
│  │  ├─ calc.py             # Calc protocol, CalcContext
│  │  ├─ validation.py       # InputSpec, validators, Issue, dependencies
│  │  ├─ loadcase.py         # LoadCase manager + governing-case selection
│  │  └─ registry.py         # pack + edition registry
│  ├─ data/
│  │  ├─ materials/          # allowable stress vs T, physical props (DB-1)
│  │  ├─ components/         # FR-CC identity + correlations
│  │  ├─ tables/             # B16.5 ratings, pipe schedules, heads, bolts, gaskets
│  │  ├─ codes/              # edition-keyed coefficient tables (DB-4)
│  │  └─ schema/             # JSON schemas + provenance header format
│  ├─ calc/                  # ASME VIII-1 core calcs (CORE-*)
│  │  ├─ shell.py            # UG-27
│  │  ├─ heads.py            # UG-32 / UG-34
│  │  ├─ external.py         # UG-28 / UG-29 / UG-30 / UG-33
│  │  ├─ openings.py         # UG-36…UG-41
│  │  ├─ mawp.py             # UG-98 / UG-99
│  │  ├─ joints.py           # UW-11 / UW-12
│  │  └─ minimums.py         # UG-16 / UG-45
│  ├─ packs/
│  │  ├─ base.py             # Pack protocol
│  │  ├─ pv/  pu/  fl/  ps/   # verified packs
│  │  └─ tk/  hx/  co/        # experimental packs
│  ├─ report/                # PDF engine + templates
│  ├─ drawing/               # DXF + PDF GA engine
│  ├─ preview3d/             # scene builder + viewer
│  ├─ gui/                   # PySide6 shell
│  ├─ persistence/           # project JSON + SQLite, autosave, undo/redo
│  └─ cli/                   # placeholder (EXT-3 is v2.0)
├─ tests/
│  ├─ golden/                # golden calc tests
│  ├─ unit/
│  └─ property/              # monotonicity, unit round-trips
└─ data_sources/             # provenance records (transcribed-on, checked-by)
```

### 3.3 Suggested library stack

| Concern | Library |
|---|---|
| GUI | PySide6 |
| Units | pint |
| Input models / validation | pydantic v2 |
| DXF | ezdxf |
| PDF report | reportlab (primary); weasyprint optional |
| PDF from DXF | ezdxf drawing add-on |
| 3D preview | pyvista (+ trimesh) |
| Fluid properties | CoolProp (pinned) |
| Persistence | JSON + SQLite |
| Tests | pytest (+ hypothesis) |

---

## 4. Feature catalog (complete)

This is the full requirement set. **[M]** = planned to v1.0; **[S]** = v1.x (noted where the roadmap pulls it forward); **[C]** = v2+ backlog.

### FR-PM — Project & data management
- PM-1 [M] Create/open/save/duplicate projects; autosave; crash recovery.
- PM-2 [M] Undo/redo across parameter edits.
- PM-3 [M] Project tree: project → equipment items → components → calculations → drawings → reports.
- PM-4 [M] Revision/versioning of an equipment item with input comparison.
- PM-5 [S] Named presets/templates.
- PM-6 [S] CSV/Excel import for parameter sweeps; export results table.
- PM-7 [S] Whole-project template library.

### FR-IN — Input, forms & validation
- IN-1 [M] All inputs via labelled forms with units, tooltips, symbol, source clause.
- IN-2 [M] Sliders for exploratory parameters; live recalc target < 100 ms.
- IN-3 [M] Unit-system toggle (SI/imperial/mixed); per-field display units.
- IN-4 [M] Validation: range checks, cross-field logic, warnings vs hard errors.
- IN-5 [M] Dependent fields greyed out with stated reason.
- IN-6 [M] Live pass/fail per calculation + overall verdict with governing load case.
- IN-7 [S] Side-by-side what-if comparison.
- IN-8 [S] Searchable input palette; recently-used values.
- IN-9 [C] Slider macros (sweeps).

### FR-DB — Material, fluid & standards database
- DB-1 [M] Material DB: allowable stress vs temperature, yield/tensile at T, density, thermal expansion, Poisson, impact-test exemption curves, PWHT rules.
- DB-2 [M] Standard component tables: pipe schedules, flange ratings, heads, bolts, gaskets, nozzle sizes, profiles.
- DB-3 [M] Fluid property entry for design case; one-click fill from FR-CC; manual allowed and flagged.
- DB-4 [M] Code coefficient/formula tables referenced by edition.
- DB-5 [M] User-extensible materials and custom entries; every custom record flagged in reports.
- DB-6 [S] Per-material corrosion/erosion defaults by service; compatibility suggestions.
- DB-7 [S] Standard-edition switcher with changed-value highlighting.
- DB-8 [C] Supplier curve/catalogue import.

### FR-CC — Chemical component database
- CC-1 [M] Built-in component set (~100–300 common chemicals) with name, synonyms, CAS, MW, formula.
- CC-2 [M] Temperature-dependent property correlations: liquid density, vapor pressure, viscosity (liq/vap), specific heat, thermal conductivity; boiling/freezing reference points.
- CC-3 [M] One-click design-case fill; each value stamped `{source, correlation, version, evaluated-at-T}`.
- CC-4 [M] Phase determination at design T/P feeding weight calcs, NPSH, flashing warnings.
- CC-5 [M] Fluid–material compatibility rules — warnings only, each with rationale + source tag.
- CC-6 [S] Ideal mixture support with "ideal-mixture estimate — verify" flag.
- CC-7 [S] User-extensible components/CSV import.
- CC-8 [S] Service screening (H₂S/CO₂/chlorides) linking to NACE MR0175.
- CC-9 [C] Simulator hand-off (Aspen/HYSYS/PRO II).
- CC-10 [M] Provenance & honesty on every row; accuracy limits surfaced.

### FR-CORE — Calculation engine & shared VIII-1 envelope
- CORE-1 [M] Deterministic pure-function calc objects producing provenance-rich results.
- CORE-2 [M] Internal pressure: UG-27 shell; UG-32 heads (ellipsoidal, torispherical, hemispherical, conical); UG-34 flat/blank; UG-98 MAWP; UW-12 joint efficiency; UW-11 NDE-reduced joint selection.
- CORE-3 [M] External pressure: UG-28/UG-33 + design-chart data; stiffening rings UG-29/UG-30.
- CORE-4 [M] Openings & reinforcement: UG-36…UG-41 area replacement, combined openings, ligament efficiency, reinforcement limits.
- CORE-5 [M] Minimum thickness: UG-16; UG-45 connection minimums.
- CORE-6 [M] Hydrostatic/proof test: UG-99, S_T/S ratio; MAWP reduction on test.
- CORE-7 [M] Load-case manager: operating / unused / test / wind / seismic / seismic+operating / maintenance; governing-case selection (UG-22).
- CORE-8 [S] Bolted-flange joint calculation (App. 2).
- CORE-9 [S] Local-load checks (WRC 107/297).
- CORE-10 [S] Fatigue screening.
- CORE-11 [C] PWHT helper (UCS-56); MDMT logic (UCS-66).

### FR-PV — Pressure vessels pack
- PV-1 [M] Vertical/horizontal wizard: shell courses, head type/size, support selection.
- PV-2 [M] Per-course thickness sizing with corrosion/erosion allowance and mill-under-tolerance.
- PV-3 [M] Nozzle schedule: size/rating, orientation, elevation, reinforcement per opening; manway selection.
- PV-4 [M] Weight & centre-of-gravity report (empty, filled, operating, test).
- PV-5 [S] Saddle (Zick), skirt base-plate/anchor, lug local loads.
- PV-6 [S] Internal attachments (tray/cyclone/packing loads).
- PV-7 [C] Water-slinging/vortex, demister, expansion joints.

### FR-TK — Storage tanks pack (API 650)
- TK-1 [M] Shell course thickness by API 650 method.
- TK-2 [M] Roof type selection + basic sizing; bottom plate layout.
- TK-3 [M] Nozzle/opening reinforcement; roof/nozzle load check.
- TK-4 [S] Wind & seismic anchorage; overturning.
- TK-5 [S] Wind girders, shell opening reinforcement, ladder/platform take-off.
- TK-6 [C] API 620 variant.

### FR-HX — Heat exchangers pack (TEMA)
- HX-1 [M] Shell & channel/cover thickness (VIII-1 + TEMA).
- HX-2 [M] Tubesheet thickness (TEMA; UHX reference flagged); tube layout + ligament efficiency.
- HX-3 [M] Tube-to-tubesheet joint strength; expansion-joint note.
- HX-4 [S] Baffle spacing/geometry; nozzle + pass-partition layout.
- HX-5 [S] Thermal growth check.
- HX-6 [C] TEMA class selector; UHX stress analysis.

### FR-FL — Flanges & nozzles pack
- FL-1 [M] Flange rating selection by material class/temperature/pressure (B16.5) with nearest-upgrade.
- FL-2 [M] Bolt/gasket selection; bolt-up checks (target torque); seating vs operating.
- FL-3 [M] Nozzle-size schedule with rating + mating-flange pair.
- FL-4 [S] Non-standard flange per App. 2.
- FL-5 [C] B16.47 series A/B; RTJ vs spiral-wound; bolt-load optimization.

### FR-PS — Piping & pipe supports pack
- PS-1 [M] Straight pipe wall thickness (B31.3 304.1.2) with weld factor, mill tolerance, CA.
- PS-2 [M] Branch/connection reinforcement (B31.3 304.3); component pressure check.
- PS-3 [M] Pressure–temperature rating verification.
- PS-4 [S] Thermal expansion/deflection (B31.3 319).
- PS-5 [S] Support selection (MSS SP-58); pipe-shoe local loads.
- PS-6 [C] Simple span calculator; PSF/occasional loads.

### FR-CO — Columns & reactors pack
- CO-1 [M] Tall-shell checks: pressure + wind/seismic combinations; skirt-transition combined stress.
- CO-2 [M] Skirt support design: base plate, anchor bolts (ACI 318), ring-beam.
- CO-3 [M] Wind/seismic moment from ASCE 7 with height/location/exposure inputs.
- CO-4 [S] Tray/packing support ring, davit, ladder loads.
- CO-5 [S] Lateral deflection/whip limits; vibration screening.
- CO-6 [C] Reactor internals checks.

### FR-PU — Pumps pack
- PU-1 [M] Duty-point input form: Q, H, fluid density/viscosity/T, NPSHa, speed, suction conditions, system head estimate.
- PU-2 [M] Type guidance: Ns/Nss → radial/mixed/axial + API 610 type class (OH/BB/VS) or B73.1 / ISO 5199 / ISO 2858 equivalent.
- PU-3 [M] Selection from catalogue; rank by efficiency margin; BEP and %BEP.
- PU-4 [M] Operating-region check (POR/AOR) with remedy (trim, model, VFD).
- PU-5 [M] NPSH check: NPSHa ≥ NPSH3 + margin (ANSI/HI 9.6.1); cavitation risk + remedies.
- PU-6 [M] Power & driver sizing: hydraulic → absorbed → motor rating with SG/API/NEMA margins; amp check.
- PU-7 [M] Casing pressure design: MAWP + wall thickness (VIII-1); hydrotest (API 610).
- PU-8 [M] Shaft check: torque + bending → combined stress; seal-chamber deflection ≤ API 610 limit (0.05 mm / 0.002 in); safety factor.
- PU-9 [M] Bearing life: L10h per ISO 281 vs API 610 minimum.
- PU-10 [M] Mechanical seal selection per API 682: category, arrangement (1/2/3), faces, secondary containment; flush plan (11/21/23/32/52/53/54); seal datasheet.
- PU-11 [M] Nozzle-load check against API 610 allowables; pass/fail per nozzle.
- PU-12 [M] Materials: API 610 material-class selection vs fluid/T; CA; sour-service notes (NACE).
- PU-13 [M] Vibration limits vs API 610.
- PU-14 [M] Datasheet output (API 610 style, PDF).
- PU-15 [M] GA drawing: pump + driver + baseplate, elevation + plan, nozzle orientation, tag block, foundation pattern.
- PU-16 [S] Curve overlay (system curve, operating point, POR/AOR shading, efficiency/power/NPSH).
- PU-17 [S] Affinity laws (trim/speed) with auto-recheck of PU-4..PU-6.
- PU-18 [S] Critical-speed screening (rule-of-thumb, flagged).
- PU-19 [S] System NPSH calculator feeding PU-5.
- PU-20 [S] Baseplate/foundation layout, anchor sizing, alignment notes.
- PU-21 [C] PD pump mini-pack.
- PU-22 [C] Curve import/digitizer.
- PU-23 [C] Parallel/series pump banks.

### FR-DR — 2D drawing generation
- DR-1 [M] Auto 2D drawing per equipment item: orthographic views, dimensions, centrelines, hatching, weld symbols, nozzle callouts.
- DR-2 [M] Annotation layer: auto-placed key results.
- DR-3 [M] Title block: project, tag, rev, scale, units, drawing number, date, drawn/checked.
- DR-4 [M] Export DXF and PDF.
- DR-5 [M] Consistent named layer scheme.
- DR-6 [S] Sheet sizes (A0–A4), title-block customization, hatch patterns.
- DR-7 [S] Dimension-driven re-layout.
- DR-8 [C] Auto dimension-chain, isometric views, round-trip import.

### FR-3D — 3D preview
- 3D-1 [M] Interactive preview (orbit/pan/zoom) from the same parameters as 2D.
- 3D-2 [M] Live update (< 2 s typical).
- 3D-3 [S] Section cutting, show/hide, pick-a-component.
- 3D-4 [S] Export STEP/STL.
- 3D-5 [C] Interference/clash check.

### FR-RP — Reporting
- RP-1 [M] One-click PDF per calculation and per equipment item.
- RP-2 [M] Report: inputs+units, material props, formula as published, substituted values, result, clause ref, pass/fail, governing case, notes, edition.
- RP-3 [M] Summary sheet: equipment data, verdict, checks with pass/fail and margins.
- RP-4 [S] Hyperlinked contents; appendix.
- RP-5 [C] JSON/CSV report export.

### FR-EXT — Export & interop
- EXT-1 [M] Export DXF, PDF, PNG, CSV (results), JSON (full project).
- EXT-2 [S] STEP export; fillable-PDF datasheets.
- EXT-3 [C] Headless CLI + Python API.

### FR-VAL — Verification & QA
- VAL-1 [M] Golden test suite vs published worked examples + hand-checks; regression on every change.
- VAL-2 [M] Status indicator: "verified" vs "experimental" per check.
- VAL-3 [S] Property-based + unit round-trip tests.
- VAL-4 [S] Known-issue/errata register per edition.
- VAL-5 [C] Third-party validation campaign.

### FR-GUI — Application shell
- GUI-1 [M] Explorer (left), forms (centre), results (right), drawing/3D tabs.
- GUI-2 [M] Status bar: overall pass/fail, governing case, unit system, editions.
- GUI-3 [M] Error/warning presentation with jump-to-field.
- GUI-4 [S] Keyboard workflow, command palette, saved layouts.
- GUI-5 [C] Dark mode.

### FR-CIT — Citation integrity
- CIT-1 [M] Every result stores `{standard, edition, clause}`.
- CIT-2 [M] No module embeds standard text/tables beyond a short quote; lint + review enforce §6.
- CIT-3 [S] Data-table provenance report.
- CIT-4 [S] Citation coverage dashboard (any [M] check lacking a source tag fails CI).

---

## 5. Core contracts (freeze before coding)

### 5.1 Provenance and status

```python
@dataclass(frozen=True)
class Citation:
    standard: str      # e.g. "ASME BPVC VIII-1"
    edition: str       # e.g. "2023"
    clause: str        # e.g. "UG-27(c)(1)"
    source_tag: str | None = None   # §10.1 tag, e.g. "S1"

class Verdict(Enum):
    PASS = "pass"; FAIL = "fail"; WARN = "warn"; NA = "n/a"

class VerificationStatus(Enum):
    VERIFIED = "verified"; EXPERIMENTAL = "experimental"
```

### 5.2 Result object

```python
@dataclass
class Result:
    symbol: str
    value: float | None
    unit: str
    formula: str                     # e.g. "t = P*R/(S*E - 0.6*P)"
    substitutions: dict[str, str]    # rendered input values
    citation: Citation
    inputs_used: list[str]
    verdict: Verdict
    margin: float | None             # e.g. (available-required)/required
    governing_case: str | None
    verification: VerificationStatus
    children: list["Result"] = field(default_factory=list)
    issues: list["Issue"] = field(default_factory=list)
```

### 5.3 Calc protocol and context

```python
@dataclass
class CalcContext:
    materials: MaterialsDB
    components: ComponentDB
    editions: CodeEdition
    units: UnitSystem

class Calc(Protocol):
    id: str
    citation: Citation
    verification: VerificationStatus
    def __call__(self, inputs, ctx: CalcContext) -> Result: ...
```

### 5.4 Pack protocol

```python
class Pack(Protocol):
    family: str
    Input: type[BaseModel]
    def validate(self, inputs) -> list[Issue]: ...
    def calculate(self, inputs, ctx: CalcContext) -> ResultTree: ...
    def draw(self, inputs, results) -> Drawing: ...
    def report(self, inputs, results) -> ReportDoc: ...
    def scene3d(self, inputs) -> Scene: ...
```

### 5.5 Input field metadata

Every input field declares metadata so IN-1/2/4/5, GUI-3, and RP-2 fall out automatically:

```
label, symbol, unit, help, clause,
slider(min,max,step), depends_on, group, severity_on_invalid
```

Implement via pydantic v2 `Field(json_schema_extra={...})`.

### 5.6 Issue object

```python
@dataclass
class Issue:
    severity: Literal["error", "warning"]
    field: str | None      # jump-to-field target (GUI-3)
    message: str
    rationale: str | None  # for CC-5 compatibility rules
    citation: Citation | None
```

---

## 6. Data & copyright policy (binding)

ASME/API/TEMA/HI/MSS standards are copyrighted. Rules apply to code, UI, reports, and data files:

1. **Cite, don't reproduce.** Clause/paragraph numbers, formula symbols, short paraphrases only. Never ship normative standard text, tables, figures, or appendices verbatim in the repo, UI, tooltips, or PDFs.
2. **Formulas are implemented as code.** Engineering formulas implemented from scratch in Python with the `{standard, edition, clause}` citation. No ASME endorsement implied; no ASME/API/TEMA/HI/MSS names/logos in branding beyond factual citation.
3. **Numeric data gets provenance, not wholesale copying.** Transcribe only the values needed; every row stamped `{source, edition, clause, transcribed-on, checked-by}`. Prefer public-domain equivalents; otherwise make large central tables user-supplied data files (DB-5).
4. **Reports quote references, not clauses.** Show `ASME VIII-1 (2023), UG-27(c)(1)` plus our substitution — never clause prose.
5. **Benchmark numbers are facts; benchmark text is not.** Golden tests may compare numeric results to published examples; example text/tables are not copied.
6. **Legal review before release** (R-2).

**Enforcement (CIT-2):** CI lint scans for reproduced standard text (blocklist + long-string detection) and fails any data file missing a provenance header. CIT-4 fails any [M] check lacking a source tag.

**External-pressure chart handling (D4):** `calc/external.py` uses published equations/curve-fits and transcribed **numeric** curve points with provenance; chart **figures** are never bundled.

---

## 7. Verification strategy

- **Golden tests** (`tests/golden/`): each test = input JSON + expected numeric results + citation + source reference. Numeric comparison with documented tolerance. Sources prioritised: NIST/NBS, NASA, NRC/OSHA, openly licensed OER, original papers; primary acceptance remains independent hand calculation.
- **Property tests** (`tests/property/`): monotonicity (thickness ↑ with pressure, ↓ with allowable stress), unit round-trip, determinism (same inputs + edition ⇒ identical result).
- **Regression:** golden suite runs on every change in CI.
- **Coverage:** ≥ 90% on calculation modules (NFR-10); 100% of [M] checks have golden tests.
- **VAL-2:** every `Calc` declares `verification`; surfaced in GUI and reports. TK/HX/CO ship `EXPERIMENTAL` in v1.0.
- **Performance:** live recalc < 100 ms (NFR-1); 3D < 2 s; report < 3 s.

---

## 8. Release plan

### 8.1 v0.5 (alpha) — platform + VIII-1 core + PV

Internal-use alpha. Platform complete enough to run a vessel end-to-end.

### 8.2 v1.0 — breadth + four verified packs

Core complete; **PV, PU, FL, PS verified**; **TK, HX, CO experimental**; CC core; report + DXF + 3D.

### 8.3 v0.5 exit criteria

- [ ] Platform works: project save/load, undo/redo, autosave, crash recovery.
- [ ] VIII-1 core calcs (CORE-2…CORE-7) implemented and golden-tested.
- [ ] PV-1…PV-4 implemented; produce report + DXF + 3D for a vessel.
- [ ] Every reported number carries `{standard, edition, clause}`.
- [ ] CIT-2 lint green; no verbatim standard text.
- [ ] Live recalc < 100 ms for a vessel.

### 8.4 v1.0 exit criteria

- [ ] All [M] items in PV, PU, FL, PS pass golden tests (VAL-1).
- [ ] 100% of reported numbers carry `{standard, edition, clause}` (CIT-1).
- [ ] CIT-2 lint passes (no verbatim text).
- [ ] Report generation < 3 s; live recalc < 100 ms (NFR-1).
- [ ] TK/HX/CO visibly marked *experimental* everywhere (VAL-2).
- [ ] ≥ 90% coverage on calculation modules (NFR-10).
- [ ] Legal review gate completed (R-2).

---

## 9. Task breakdown

Format per task: **What** (deliverable), **How** (build approach), **Done when** (acceptance), **FR** (traceability), **Depends**.

### 9.0 Phase 0 — Foundations (≈1 week)

#### P0-T1 — Repo scaffold, packaging, CI
- **What:** `pyproject.toml`, `src/pemds` layout, dev deps, CI workflow, pre-commit, pytest config.
- **How:** hatchling/setuptools; `pytest`, `ruff`, `mypy`, `hypothesis`; CI runs lint + type-check + tests; matrix on Python 3.12. Pin all runtime deps (NFR-2).
- **Done when:** `pip install -e .[dev]` works; CI green on empty test suite.
- **FR:** NFR-9/10.

#### P0-T2 — Copyright lint (CIT-2 / CIT-4)
- **What:** CI check for verbatim standard text + provenance-header requirement + source-tag coverage.
- **How:** script scans `src/` and `data/` for (a) blocklisted phrases, (b) strings over a length threshold resembling prose, (c) data files missing a provenance header, (d) `Calc` objects lacking a `citation`. Integrate into CI as a required job.
- **Done when:** CI fails on a seeded violation and passes on clean tree.
- **FR:** CIT-2, CIT-4, R-2.

#### P0-T3 — Freeze core contracts
- **What:** `core/provenance.py`, `core/result.py`, `core/calc.py`, `core/validation.py`, `packs/base.py`.
- **How:** implement §5 dataclasses/protocols verbatim; unit tests for serialisation round-trip; document in docstrings.
- **Done when:** contracts import, serialise/deserialise, and are used by a trivial dummy calc + pack.
- **FR:** CORE-1, CIT-1.

#### P0-T4 — Data provenance format
- **What:** JSON schema for data files + header record.
- **How:** header `{source, edition, clause, licence, transcribed_on, checked_by}`; schemas for materials, tables, components; loader validates on startup.
- **Done when:** loader rejects a file missing a header; sample files pass.
- **FR:** DB-4, CIT-3, §6.

#### P0-T5 — Edition registry
- **What:** `core/registry.py` mapping standard → edition → data paths.
- **How:** editions from D1; single lookup used by every calc and report; designed for DB-7 additions.
- **Done when:** calcs resolve an edition and citations carry it.
- **FR:** DB-4, DB-7 (foundation), CIT-1.

#### P0-T6 — Data & copyright policy doc
- **What:** `docs/data-policy.md` encoding §6 operationally.
- **How:** per-table transcription workflow, reviewer sign-off, storage rules.
- **Done when:** reviewed and referenced by P0-T2.
- **FR:** R-2, CIT-2/3.

#### P0-T7 — Golden-test harness
- **What:** test loader + comparator + result capture format.
- **How:** JSON fixtures `{inputs, expected, citation, source}`; tolerance config; pytest parametrisation over fixtures.
- **Done when:** one sample golden test passes.
- **FR:** VAL-1.

---

### 9.1 v0.5 sprints

#### Sprint 5-1 — Spine (units, provenance, validation, persistence, GUI shell, materials seed, UG-27)

##### S5-1-T1 — Units subsystem
- **What:** `core/units.py` — SI internal, display conversion.
- **How:** wrap `pint`; internal floats always SI; convert at input/render boundary; per-field display unit; round-trip tests.
- **Done when:** SI↔imperial↔mixed round-trips within tolerance; no unit objects inside calc hot path.
- **FR:** IN-3, NFR-3/4.

##### S5-1-T2 — Persistence + undo/redo
- **What:** `persistence/` project model, JSON+SQLite store, autosave, crash recovery, undo/redo.
- **How:** pydantic project model → JSON (portable) + SQLite (index/autosave); command pattern for undo/redo; autosave every ≥ 60 s; journal for crash recovery; schema versioning/migration.
- **Done when:** create/save/open/duplicate; undo/redo across edits; simulated crash recovers.
- **FR:** PM-1…4, NFR-6.

##### S5-1-T3 — GUI shell skeleton
- **What:** `gui/` — explorer, forms, results panel, status bar, tabs.
- **How:** PySide6; Qt model/view for project tree; forms auto-generated from pydantic metadata (§5.5); results panel renders `ResultTree`; status bar reads overall verdict + editions.
- **Done when:** a dummy pack's inputs render as forms and results display.
- **FR:** GUI-1/2/3.

##### S5-1-T4 — Validation layer
- **What:** range checks, cross-field logic, warnings vs errors, dependent greying.
- **How:** validators attached to input metadata; `Issue` severity; errors block calculation but not navigation; `depends_on` drives greying with stated reason.
- **Done when:** invalid input blocks calc and shows styled error with jump-to-field; warning does not block.
- **FR:** IN-1/4/5, GUI-3.

##### S5-1-T5 — Materials DB seed + loader
- **What:** ~10–20 common steels with allowable stress vs temperature + provenance.
- **How:** JSON per §P0-T4; each row `{source, edition, clause, transcribed-on, checked-by}`; loader + query API.
- **Done when:** a calc can look up allowable stress at temperature with provenance attached.
- **FR:** DB-1, DB-4.

##### S5-1-T6 — UG-27 shell (CORE-2 part 1)
- **What:** circumferential + longitudinal shell thickness and MAWP.
- **How:** implement UG-27(c)(1) `t = PR/(SE − 0.6P)` and (c)(2) `t = PR/(2SE + 0.4P)`; invert for MAWP; pure `Calc`; provenance result with formula + substitutions; golden test from a public-domain example.
- **Done when:** golden test passes; result shows formula, substitution, citation, verdict.
- **FR:** CORE-2, CIT-1, VAL-1.

#### Sprint 5-2 — VIII-1 part 1 (heads, joints, MAWP, minimums, hydrotest) + live recalc

##### S5-2-T1 — Heads (UG-32 / UG-34)
- **What:** ellipsoidal, torispherical, hemispherical, conical (UG-32); flat/blank (UG-34).
- **How:** implement `t = PD/(2SE−0.2P)` (elliptical), `0.885PL/(SE−0.1P)` (torispherical), `PL/(2SE−0.2P)` (hemispherical), conical rules (UG-32(f)), flat `t = d√(CP/SE)` with C from edition table; pure calcs; golden tests.
- **Done when:** each head type returns thickness + MAWP with provenance and passes golden tests.
- **FR:** CORE-2, VAL-1.

##### S5-2-T2 — Joints (UW-11 / UW-12)
- **What:** joint efficiency E lookup + NDE-reduced selection.
- **How:** edition-keyed table of E by joint type + radiographic extent; user selects NDE level; E feeds all thickness calcs; table carries provenance.
- **Done when:** E selection changes thickness correctly; golden test matches published joint-efficiency example.
- **FR:** CORE-2.

##### S5-2-T3 — MAWP (UG-98) + minimums (UG-16/UG-45)
- **What:** governing MAWP across components; minimum thickness rules.
- **How:** compute MAWP per component, take minimum; UG-16 general minimum, UG-45 connection minimums; report governing component.
- **Done when:** vessel MAWP = min component MAWP with governing case named.
- **FR:** CORE-2, CORE-5.

##### S5-2-T4 — Hydrotest (UG-99)
- **What:** test pressure + S_T/S ratio + MAWP reduction on test.
- **How:** `P_T = 1.3 × MAWP × (S_T/S)`; report test pressure and any MAWP reduction.
- **Done when:** golden test matches published UG-99 example.
- **FR:** CORE-6.

##### S5-2-T5 — Live-recalc pipeline + sliders
- **What:** < 100 ms recalculation on parameter change.
- **How:** float-SI fast path (no pint objects in hot loop); debounce slider events; incremental recalc where possible; background thread for anything > 100 ms; profile with a representative vessel.
- **Done when:** full vessel recalc measured < 100 ms; sliders update live.
- **FR:** IN-2, NFR-1.

#### Sprint 5-3 — VIII-1 part 2 (external pressure) + materials expansion

##### S5-3-T1 — External pressure (UG-28 / UG-33)
- **What:** external-pressure design for shells + heads.
- **How:** implement UG-28 iterative method using `A`/`B` factors; obtain `A`/`B` from **numeric curve data** (published equations/curve-fits + transcribed points with provenance), never chart figures (D4); golden tests against public-domain examples.
- **Done when:** externally-pressured shell/head passes golden tests; chart data documented with provenance.
- **FR:** CORE-3, D4, VAL-1.

##### S5-3-T2 — Stiffening rings (UG-29 / UG-30)
- **What:** ring design + transition rules.
- **How:** implement ring moment-of-inertia and spacing rules; integrate with UG-28.
- **Done when:** ring design returns required I + spacing with provenance.
- **FR:** CORE-3.

##### S5-3-T3 — Materials DB expansion
- **What:** expand to ~20–30 common steels + physical properties.
- **How:** allowable stress vs T, yield/tensile at T, density, thermal expansion, Poisson; per-row provenance; loader tests.
- **Done when:** PV calc can select from the expanded set with correct properties.
- **FR:** DB-1.

#### Sprint 5-4 — Openings + PV pack + report engine

##### S5-4-T1 — Openings & reinforcement (UG-36…UG-41)
- **What:** area-replacement method; combined openings; ligament efficiency; reinforcement limits.
- **How:** implement `A = d·t_r`; `A1+A2+A3 ≥ A`; limits of reinforcement; ligament efficiency; pure calcs; golden tests.
- **Done when:** nozzle reinforcement check passes golden tests and reports pass/fail + margin.
- **FR:** CORE-4, VAL-1.

##### S5-4-T2 — PV pack (PV-1…PV-4)
- **What:** vessel wizard, per-course sizing, nozzle schedule, weight/CoG.
- **How:** implement `Pack`; vertical/horizontal; shell courses + head + support selection; corrosion/erosion allowance + mill tolerance; nozzle schedule with per-opening reinforcement; weight/CoG for empty/filled/operating/test.
- **Done when:** a full vessel runs end-to-end and produces a `ResultTree`.
- **FR:** PV-1…4.

##### S5-4-T3 — Report engine (RP-1…RP-3)
- **What:** one-click PDF with formula trace + summary sheet.
- **How:** `reportlab`; render each `Result` as inputs, formula-as-published, substituted values, result, citation, verdict, governing case; summary sheet with overall verdict + margins; generation < 3 s.
- **Done when:** vessel report PDF contains full trace; all numbers carry citations.
- **FR:** RP-1/2/3, NFR-1.

#### Sprint 5-5 — Output + verification + v0.5 exit

##### S5-5-T1 — Drawing engine (DR-1…DR-5)
- **What:** GA DXF + PDF.
- **How:** `ezdxf` parametric GA (vessel elevation/plan, dimensions, centrelines, hatching, nozzle callouts); named layers; title block; export DXF and PDF (ezdxf drawing add-on).
- **Done when:** a vessel produces a valid DXF (opens in LibreCAD) + PDF.
- **FR:** DR-1…5, EXT-1.

##### S5-5-T2 — 3D preview (3D-1/3D-2)
- **What:** interactive preview + live update.
- **How:** `pyvista`; build scene from same parameters as 2D (shells, heads, nozzles, supports); orbit/pan/zoom; regenerate < 2 s.
- **Done when:** preview renders and updates on parameter change.
- **FR:** 3D-1/2, NFR-1.

##### S5-5-T3 — VAL-1/2 harness wiring
- **What:** verification status plumbed GUI + report.
- **How:** each `Calc` declares `verification`; GUI badge + report line; v0.5 checks all `VERIFIED`.
- **Done when:** status appears in GUI and PDF.
- **FR:** VAL-2.

##### S5-5-T4 — v0.5 exit validation
- **What:** run §8.3 checklist.
- **How:** golden regression + perf measurement + CIT-2 lint + manual end-to-end vessel.
- **Done when:** all v0.5 exit boxes ticked.
- **FR:** §8.3.

---

### 9.2 v1.0 sprints

#### Sprint 10-1 — FR-CC core (CC-1…CC-5, CC-10)

##### S10-1-T1 — Component identity DB (CC-1)
- **What:** ~100 common chemicals: name, synonyms, CAS, MW, formula.
- **How:** bundle JSON sourced from NIST Chemistry WebBook (public domain) + CoolProp fluid mapping; provenance per row; searchable loader.
- **Done when:** ≥ 100 components load and are searchable by name/CAS/synonym.
- **FR:** CC-1, CC-10.

##### S10-1-T2 — Property correlations (CC-2)
- **What:** density, vapour pressure, viscosity (liq/vap), specific heat, thermal conductivity vs T; boiling/freezing reference points.
- **How:** hybrid (D7): CoolProp evaluation engine (pinned version) + own identity DB; wrap in a `ComponentDB`; stamp `{source, correlation, version}`; surface accuracy limits.
- **Done when:** properties evaluate at design T with provenance; spot-checked against NIST.
- **FR:** CC-2, CC-10, D7.

##### S10-1-T3 — One-click design-case fill (CC-3) + phase determination (CC-4)
- **What:** fill DB-3 fields from component+T(+P); liquid/vapour/two-phase flag.
- **How:** evaluate correlations at T/P; populate design case; phase from CoolProp; feed weight calcs, NPSH, flashing warnings.
- **Done when:** picking a component + T fills the design case and sets phase, all stamped.
- **FR:** CC-3, CC-4, DB-3.

##### S10-1-T4 — Compatibility rules (CC-5)
- **What:** rule-based fluid–material warnings.
- **How:** rule table (chlorides vs austenitic SS, HF/HCl limits, CS low-temperature) with rationale + source tag each; `Issue` severity = warning only; UI tooltips.
- **Done when:** selecting an incompatible pair produces a warning with rationale + source.
- **FR:** CC-5.

##### S10-1-T5 — CC provenance & honesty (CC-10)
- **What:** no bare numbers; report states property source + evaluation T; accuracy in tooltips.
- **How:** extend `Result` provenance for component values; report string "property data: CoolProp vX / NIST WebBook, evaluated at T".
- **Done when:** every component value in results/reports shows source + T.
- **FR:** CC-10.

#### Sprint 10-2 — Pump pack part 1 (PU-1…PU-9)

##### S10-2-T1 — Duty-point form + type guidance (PU-1, PU-2)
- **What:** duty inputs; Ns/Nss → pump type recommendation.
- **How:** pydantic input model; compute specific speed `Ns = N√Q/H^(3/4)` and `Nss`; map ranges to radial/mixed/axial + API 610 type class (or B73.1/ISO equivalent); cite clause.
- **Done when:** given a duty point, type guidance returns with citation.
- **FR:** PU-1/2.

##### S10-2-T2 — Selection + operating-region check (PU-3, PU-4)
- **What:** match duty against sample curves; BEP/%BEP; POR/AOR check + remedy.
- **How:** sample curve DB (H-Q, η, power, NPSH vs Q); interpolate; rank by efficiency margin; POR (typically 70–120% BEP) and AOR checks per API 610; suggest trim/model/VFD.
- **Done when:** selection returns a ranked candidate; out-of-region point warns with remedy.
- **FR:** PU-3/4, D5.

##### S10-2-T3 — NPSH + power/driver sizing (PU-5, PU-6)
- **What:** NPSHa ≥ NPSH3 + margin; hydraulic→absorbed→motor rating.
- **How:** ANSI/HI margin; `P_hyd = ρgQH`; `P_abs = P_hyd/η`; apply SG + API 610/NEMA margins; amp check; flag cavitation.
- **Done when:** NPSH and power checks report margins + pass/fail with citations.
- **FR:** PU-5/6.

##### S10-2-T4 — Casing + shaft + bearings (PU-7, PU-8, PU-9)
- **What:** casing MAWP/thickness + hydrotest; shaft combined stress + seal-chamber deflection limit; bearing L10h.
- **How:** casing via VIII-1 method; shaft torque + bending → combined stress, deflection ≤ 0.05 mm / 0.002 in; `L10h = (10^6/(60n))·(C/P)^p` per ISO 281 vs API 610 minimum; report safety factors.
- **Done when:** all three checks return with pass/fail + margins and citations.
- **FR:** PU-7/8/9.

#### Sprint 10-3 — Pump pack part 2 (PU-10…PU-15) + output

##### S10-3-T1 — Seal selection + datasheet (PU-10)
- **What:** API 682 category/arrangement/faces/containment; flush plan; seal datasheet.
- **How:** rule engine mapping fluid/T/pressure → category, arrangement 1/2/3, face materials, flush plan (11/21/23/32/52/53/54); render datasheet doc.
- **Done when:** a duty yields a seal recommendation with reasoning + datasheet.
- **FR:** PU-10.

##### S10-3-T2 — Nozzle loads + materials + vibration (PU-11, PU-12, PU-13)
- **What:** nozzle-load check; material-class selection; vibration limit check.
- **How:** compare entered F/M against API 610 allowables per nozzle; map material class (S-6, C-6, A-7…) vs fluid/T; NACE sour-service flags; vibration velocity vs API 610 range.
- **Done when:** all three report pass/fail per item with citations.
- **FR:** PU-11/12/13.

##### S10-3-T3 — Pump datasheet + GA drawing (PU-14, PU-15)
- **What:** API 610-style datasheet PDF; GA drawing (elevation + plan).
- **How:** report template populated from results; `ezdxf` GA with pump+driver+baseplate, nozzle orientation/elevations, tag block, foundation/anchor pattern.
- **Done when:** datasheet + GA produced and included in equipment output.
- **FR:** PU-14/15, DR-1…5.

##### S10-3-T4 — Pump report + drawing integration
- **What:** pump full calculation report + drawings registered in project tree.
- **How:** extend report engine; register `Drawing[]`/`Datasheet[]` in persistence model.
- **Done when:** pump equipment emits report + datasheet + GA in one action.
- **FR:** RP-1/3, PM-3.

#### Sprint 10-4 — FL + PS verified packs

##### S10-4-T1 — FL pack (FL-1…FL-3)
- **What:** flange rating selection; bolt/gasket + target torque; nozzle-size schedule.
- **How:** B16.5 rating tables (provenance, minimal transcription); material class + T + P lookup with nearest-upgrade; gasket/bolt selection; target torque; mating-flange pairs.
- **Done when:** given size/class/material/T/P, selects a flange and reports rating + bolts/gasket with citation.
- **FR:** FL-1/2/3.

##### S10-4-T2 — PS pack (PS-1…PS-3)
- **What:** straight-pipe wall thickness; branch reinforcement; P-T rating verification.
- **How:** B31.3 304.1.2 `t = PD/(2(SE + PY))` + mill tolerance + CA; 304.3 branch reinforcement; component P-T rating check.
- **Done when:** pipe/branch checks pass golden tests; P-T verification reports pass/fail.
- **FR:** PS-1/2/3.

#### Sprint 10-5 — Experimental packs (TK, HX, CO) + badges

##### S10-5-T1 — TK minimal (TK-1…TK-3)
- **What:** one governing shell thickness check, roof type basic sizing, basic opening check.
- **How:** API 650 shell method (height, SG, stress, joint efficiency, mill tolerance); implement core [M] check; mark `EXPERIMENTAL`; golden test where possible.
- **Done when:** tank shell check runs and is flagged experimental everywhere.
- **FR:** TK-1/2/3, VAL-2.

##### S10-5-T2 — HX minimal (HX-1…HX-3)
- **What:** shell/channel thickness, tubesheet thickness (TEMA), tube-to-tubesheet joint check.
- **How:** reuse VIII-1 for shell; TEMA tubesheet formula with UHX reference flagged; joint strength check; `EXPERIMENTAL`.
- **Done when:** HX governing checks run, experimental-flagged.
- **FR:** HX-1/2/3, VAL-2.

##### S10-5-T3 — CO minimal (CO-1…CO-3)
- **What:** tall-shell pressure check + one wind/seismic moment check + skirt transition check.
- **How:** reuse VIII-1 envelope; ASCE 7 pressure profile → moment with height/location/exposure; combined stress at skirt transition; `EXPERIMENTAL`.
- **Done when:** column governing checks run, experimental-flagged.
- **FR:** CO-1/2/3, VAL-2.

##### S10-5-T4 — Experimental badge propagation (VAL-2)
- **What:** "experimental" visibly marked in GUI, results, reports, drawings for TK/HX/CO.
- **How:** `VerificationStatus` drives badge in GUI, report header, drawing annotation.
- **Done when:** every TK/HX/CO surface shows the experimental label.
- **FR:** VAL-2.

#### Sprint 10-6 — Harden + v1.0 exit

##### S10-6-T1 — PV [M] completion + load-case manager
- **What:** finish all PV [M]; full CORE-7 load-case manager.
- **How:** operating/unused/test/wind/seismic/seismic+operating/maintenance; UG-22 governing-case selection feeding verdicts.
- **Done when:** PV [M] complete; governing case named in results.
- **FR:** PV-1…4, CORE-7.

##### S10-6-T2 — Export (EXT-1)
- **What:** DXF, PDF, PNG, CSV, JSON export.
- **How:** project JSON export; results CSV; preview PNG; drawings DXF/PDF already available; wire export actions in GUI.
- **Done when:** all five formats export from a project.
- **FR:** EXT-1.

##### S10-6-T3 — Coverage + golden completion
- **What:** ≥ 90% coverage on calc modules; golden tests for every [M] check in PV/PU/FL/PS.
- **How:** fill test gaps; CI coverage gate; ensure every `Calc` has a fixture.
- **Done when:** coverage ≥ 90%; all [M] verified-pack checks covered.
- **FR:** NFR-10, VAL-1.

##### S10-6-T4 — Performance validation
- **What:** confirm recalc < 100 ms, 3D < 2 s, report < 3 s.
- **How:** benchmark suite in CI with thresholds; profile regressions.
- **Done when:** benchmarks pass.
- **FR:** NFR-1.

##### S10-6-T5 — v1.0 exit validation + legal review gate
- **What:** run §8.4 checklist; complete R-2 legal review.
- **How:** manual end-to-end across all seven families; CIT lint; coverage; sign-off.
- **Done when:** all §8.4 boxes ticked and legal review recorded.
- **FR:** §8.4, R-2.

---

## 10. Cross-cutting tracks

| Track | Applies to | Mechanism |
|---|---|---|
| Verification | All calcs | Golden + property tests, CI regression, VAL-2 status |
| Copyright | All data/code/UI/reports | CIT-2 lint + provenance headers + review |
| Determinism | All calcs | Pinned deps, float64, documented rounding (NFR-2/4) |
| Performance | Live recalc, 3D, reports | Float-SI fast path, background threads, CI benchmarks |
| Offline-first | Whole app | Local data files; no runtime network (NFR-8) |

---

## 11. Risks

| # | Risk | Mitigation in this plan |
|---|---|---|
| R-1 | Scope breadth | Breadth-first phasing; experimental labelling; v1.0 verified set fixed to PV/PU/FL/PS |
| R-2 | Copyright | CIT-2/4 enforcement from v0.5; data policy (P0-T6); legal gate (S10-6-T5) |
| R-3 | Edition drift | Edition registry (P0-T5); DB-7 later; edition stamped on reports |
| R-4 | Engineering liability | VAL-2 status + report disclaimer from v0.5 |
| R-5 | Pump data availability | Sample curves (D5); import path is v2.0 |
| R-6 | 3D preview cost | Simple preview scope (3D-1); can lag drawings |
| R-7 | Property-data accuracy | CC-10 provenance + accuracy flags; warnings not errors; CC-7 override later |

---

## 12. Out of scope for v1.0

Process simulation/sizing; detailed 3D CAD modelling; FEA; Div 2 / EN 13445 / PD 5500 / IS 2825 calc sets; electrical/motor internal design; control-system design; regulatory filing. Deferred [S]/[C] items are staged for v1.1+ per `version-roadmap.md`.

---

*Spec references use FR IDs from `functional_requirment.md`; cite them in issues and tests (e.g. "PU-8 golden test", "S10-2-T4"). Source tags resolve via FR §10.1.*
