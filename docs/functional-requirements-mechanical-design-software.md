# Functional Requirements Specification
## Process Equipment Mechanical Design Suite (working name: "PEMDS")

**Status:** Draft v0.4 — brainstorm-derived; scope trimmed (PM-8, PU-24, DR-8 BOM, RP-4 branding, i18n removed); clause-level sources added (§10); chemical component database added (FR-CC)
**Date:** 2026-10-02
**Language/runtime:** Python 3.12+
**Primary user:** Chemical / process engineer
**Interaction model:** Desktop GUI (forms, sliders, tables) — no coding required
**v1 emphasis:** Engineering analysis first, with 2D drawings + 3D preview + calculation reports all shipped in v1

---

## 1. Product vision

A Python application where a chemical engineer enters the duty, geometry, loads, and material for process equipment via forms and sliders; the software executes code-based mechanical design calculations live; and it emits:

1. **Live pass/fail analysis** in the GUI,
2. **A calculation report (PDF)** with full formula trace and code-clause references,
3. **A 2D engineering drawing (DXF/PDF)** — fabrication/GA style,
4. **A simple 3D preview** for geometry sanity-checking.

It is a lightweight, Python-native, friendlier alternative to PV Elite / Compress / DesignCalcs — covering the pressure-containing and structural side of process equipment (not process simulation).

### Equipment families in scope (7)

| # | Family | Governing standard(s) |
|---|---|---|
| 1 | Pressure vessels | ASME BPVC Section VIII Div 1 [S1] (UG-27 shell, UG-28 external pressure, UG-32/34 heads, UG-36–UG-40 openings, UG-99 hydrotest, App. 2 flanges, UW-11/12 joints) |
| 2 | Storage tanks | API 650 (atmospheric) / API 620 (low pressure) [S5] — *not* ASME VIII |
| 3 | Heat exchangers | ASME VIII Div 1 **+ TEMA** (R/C/S) [S1][S6], UHX tubesheets |
| 4 | Flanges / nozzles | ASME B16.5 / B16.47 (standard), VIII App. 2 (non-standard), B16.20 gaskets [S1][S3] |
| 5 | Piping & pipe supports | ASME B31.3 / B31.1 (wall thickness ~para 304) [S4], MSS SP-58 supports [S12], AISC for structural steel [S11] |
| 6 | Columns / reactors | ASME VIII Div 1 [S1] **+ wind/seismic (ASCE 7)** [S10] for tall shells; tray/packing support checks |
| 7 | **Pumps (new)** | **API 610 / ISO 13709 [S7], ASME B73.1 / ISO 5199 / ISO 2858 [S18], API 682 (seals) [S8], ANSI/HI [S9], NEMA MG-1 [S16]** |

> **Architectural consequence:** one shared pressure-envelope + drawing + reporting core (ASME VIII Div 1), plus per-family "packs" that add their own standards, inputs, and checks. All seven families share ~70% of the machinery.

### Honest scope note

The six original families do not share one code, and **pumps are a different species again**: a pump is normally *purchased*, not *designed*, so the pump pack's job is **duty-based selection + mechanical verification + datasheet + GA drawing** — not impeller hydraulic design or rotordynamics-grade rotor analysis. See §7.3 for what the pump pack does and does not attempt.

---

## 2. Users & core use cases

| Persona | Needs |
|---|---|
| Chemical engineer (primary) | Size/verify equipment from process data; produce a calc report a reviewer will accept; get a GA drawing for layout |
| Reviewer / checker | Trace every number back to inputs + code clause; see pass/fail and governing load case |
| (later) CAD drafter | Import DXF output, clean up, add title-block conventions |
| (later) Automation | Headless CLI / Python API called from another pipeline |

**Primary use cases**
- UC-1: "Enter a vessel duty (pressure, temperature, corrosion allowance, material) → get required shell/head thickness, MAWP, nozzle reinforcement check, hydrotest → PDF report + DXF drawing."
- UC-2: "Enter a pump duty (flow, head, fluid, NPSHa) → get pump selection, NPSH/power/motor checks, seal recommendation, nozzle-load check → API 610 datasheet + GA drawing."
- UC-3: "Slide a parameter and watch pass/fail update live."
- UC-4: "Sweep a parameter family from a CSV to generate many variants."

---

## 3. Architecture principles

1. **Core + packs.** Shared modules: units, materials DB, calculation engine, report engine, drawing engine, 3D preview, GUI shell. Each equipment family is a plug-in "pack".
2. **Calculation = pure function.** `Calc(inputs, materials, code_version) -> Results` — no I/O, fully deterministic, unit-safe. GUI and reports are just renderers of the same result object.
3. **Every number carries provenance.** Result objects store: symbol, value, units, formula string, substituted values, code clause reference, inputs used, pass/fail, governing case.
4. **Standards are data, not code — with provenance.** Formula coefficients, allowable-stress tables, flange-rating tables, pipe schedules live in versioned data files; the code references them by edition. Every derived table carries provenance metadata `{standard, edition, clause, transcribed-on, checked-by}` and is never presented as the standard's own text or table (see §10).
5. **Units handled internally in one system (SI), converted at the edge** with explicit display-unit control.

**Suggested (non-binding) Python stack:** PySide6 or NiceGUI (GUI), `pint` (units), `pydantic` (input models), `ezdxf` (DXF), `reportlab`/`weasyprint` (PDF report), `pyvista`/`trimesh` (3D preview), `cadquery`/`build123d` (3D geometry for preview + optional STEP), SQLite or JSON+SQLite (persistence), `pytest` (verification).

---

## 4. Functional requirements — platform modules

Priority: **M** = must (v1), **S** = should (v1.x), **C** = could (v2+). Bracketed **[S#]** tags map to the source list in §10. Platform modules (PM, IN, 3D, RP, EXT, GUI) derive from no external design standard; FR-CC derives from open property-data sources instead (§10.1).

### FR-PM — Project & data management
- PM-1 [M] Create / open / save / duplicate projects; autosave; crash recovery.
- PM-2 [M] Undo/redo across parameter edits.
- PM-3 [M] Project tree: project → equipment items → components → calculations → drawings → reports.
- PM-4 [M] Revision/versioning of an equipment item with comparison of inputs between revisions.
- PM-5 [S] Named presets/templates (e.g. "vertical vessel, skirt support", "OH2 pump skid").
- PM-6 [S] CSV/Excel import to drive a family of variants (parameter sweep); export results table.
- PM-7 [S] Template library for whole projects (title blocks, default materials, default corrosion allowance).

### FR-IN — Input, forms & validation
- IN-1 [M] All inputs entered via **forms**: grouped, labeled, with units, tooltips explaining the symbol, and the code clause it feeds.
- IN-2 [M] **Sliders** for exploratory parameters with live recalculation on change (target: <100 ms for a full equipment recalc).
- IN-3 [M] Unit-system toggle (SI / imperial / mixed) with consistent internal conversion; display units per field.
- IN-4 [M] Validation layer: range checks, cross-field logic (e.g. nozzle cannot exceed shell diameter), **warnings vs hard errors** distinctly styled; invalid inputs block calculation but not navigation.
- IN-5 [M] Dependent fields: irrelevant inputs greyed out with a stated reason ("ignored for hemispherical head").
- IN-6 [M] Live pass/fail indicator per calculation and an overall equipment verdict, with the governing load case named.
- IN-7 [S] Side-by-side "what-if" comparison of two parameter sets.
- IN-8 [S] Searchable input palette and recently-used values.
- IN-9 [C] Slider macros ("sweep corrosion allowance 0–5 mm").

### FR-DB — Material, fluid & standards database
**Sources:** [S2] for allowable-stress & physical-property tables; [S3] for pipe dimensions/schedules and flange rating tables; [S1] UCS-66/UCS-56 for impact-exemption and PWHT logic; every other coefficient table cites its own standard+edition (§10).
- DB-1 [M] Material database: allowable stress vs temperature, yield/tensile at temperature, density, thermal expansion, Poisson, impact-test exemption curves (e.g. UCS-66 [S1]), PWHT rules.
- DB-2 [M] Standard component tables: pipe schedules, flange ratings (B16.5 classes), heads, bolts, gaskets, nozzle sizes, standard profiles.
- DB-3 [M] Fluid property entry for the design case (density, viscosity, corrosivity, phase) — populated one-click from the chemical component database (FR-CC) or entered manually; manual values always allowed and flagged "user-entered".
- DB-4 [M] Code coefficient/formula tables referenced by edition.
- DB-5 [M] User-extensible: add company materials and custom entries; every custom record flagged and shown in reports.
- DB-6 [S] Per-material corrosion/erosion allowance defaults by service; material compatibility suggestions vs fluid (delegated to CC-5 rules when the fluid comes from FR-CC).
- DB-7 [S] Standard-edition switcher (e.g. VIII-1 2023 vs 2021) with changed-value highlighting.
- DB-8 [C] Supplier curve/catalogue import (pump curves: CSV/digitized PDF).

### FR-CC — Chemical component database
**Scope:** built-in, offline, open-source-sourced property library — *not* a process simulator. **Sources:** [S22] CoolProp (MIT licence) and [S23] NIST Chemistry WebBook (US Government work) for component identity & property correlations; correlation forms from published literature [S24]; provenance rules per §10.2.

- CC-1 [M] **Built-in component set:** ~100–300 common process chemicals (water, common solvents, acids/bases, light/heavy hydrocarbons, refrigerants, common gases), each with name, synonym list, CAS number, molecular weight, and formula.
- CC-2 [M] **Temperature-dependent property correlations** per component: liquid density, vapor pressure, dynamic/kinematic viscosity (liquid and vapor), specific heat, thermal conductivity; boiling/freezing point reference values.
- CC-3 [M] **One-click design-case fill:** pick component + temperature (and pressure) → populate DB-3 fields with values evaluated from the correlations; every value stamped `{source, correlation, version, evaluated-at-T}`.
- CC-4 [M] **Phase determination** at design T/P (liquid / vapor / two-phase flag) feeding vessel weight calcs, pump NPSH (vapor pressure is mandatory input to PU-5/PU-19), and flashing warnings.
- CC-5 [M] **Fluid–material compatibility rules:** rule-based warnings when the selected body material meets an incompatible/undesirable fluid (e.g. chlorides vs austenitic stainless, HF/HCl service limits, carbon-steel low-temperature limits); **warnings, never hard errors** — every rule carries its own rationale + source tag.
- CC-6 [S] **Mixture support:** ideal/idealized mixing rules for binary and multi-component blends with an explicit "ideal-mixture estimate — verify" flag on all results; no flash calculations (out of scope).
- CC-7 [S] **User-extensible:** add/override components, import property tables (CSV), bulk import of a user's own correlation set; custom rows flagged like DB-5.
- CC-8 [S] **Service screening:** presence of H₂S/CO₂/chlorides → sour-service / SCC reminders linking to NACE MR0175 [S14] (PU-12) and material-choice warnings.
- CC-9 [C] **Simulator hand-off:** import property packets exported from Aspen/HYSYS/PRO/II (CSV/JSON) and use them as a project-local component source.
- CC-10 [M] **Provenance & honesty:** no bare numbers — every component and property row carries `{source, licence, correlation/reference, version, added-on}`; reports state "property data: CoolProp vX / NIST WebBook, evaluated at T"; correlation accuracy limits surfaced in tooltips (this is engineering-estimate data, not lab measurement).

### FR-CORE — Calculation engine & shared ASME VIII-1 envelope
**Sources:** [S1] throughout — each calculation cites its clause inline below; external-pressure design-chart location confirmed against the selected edition; [S13] for local loads.
- CORE-1 [M] Deterministic, pure-function calculation objects producing the provenance-rich result structure (§3.3).
- CORE-2 [M] Internal pressure: shell (UG-27), heads — ellipsoidal, torispherical, hemispherical, conical (UG-32), flat/blank (UG-34), MAWP determination (UG-98), joint efficiency (UW-12) and NDE-reduced joint selection (UW-11).
- CORE-3 [M] External pressure: UG-28/UG-33 with the VIII-1 external-pressure design charts (chart appendix confirmed against edition), stiffening-ring design & transition (UG-29/UG-30).
- CORE-4 [M] Openings & reinforcement: area-replacement method (UG-36 through UG-41), combined openings, ligament efficiency, reinforcement limits.
- CORE-5 [M] Minimum thickness rules (UG-16, UG-45 for connection-based minimums).
- CORE-6 [M] Hydrostatic/proof test pressure (UG-99, ST/S ratio) and MAWP reduction on test.
- CORE-7 [M] Load-case manager: operating / unused / test / wind / seismic / seismic+operating / maintenance, with governing-case selection (UG-22).
- CORE-8 [S] Bolted-flange joint calculation (VIII-1 App. 2): gasket properties, bolt load, flange moments, hub stresses.
- CORE-9 [S] Local-load checks: WRC 107/297 for nozzle/shell junctions from external piping and supports.
- CORE-10 [S] Fatigue screening (VIII-1 UG-22 note / Div 2 Part 5 method [S21]) — screen, then warn "use Div 2".
- CORE-11 [C] PWHT decision helper (UCS-56), MDMT logic (UCS-66 curves).

### FR-PV — Pressure vessels pack
**Sources:** [S1] envelope & nozzle rules; [S17] saddle (Zick) method; [S11] base plates/anchors; [S13] local loads.
- PV-1 [M] Vertical/horizontal vessel wizard: shell courses, head type/size, skirt or saddle or legs support selection.
- PV-2 [M] Per-course thickness sizing with corrosion/erosion allowance and mill-under-tolerance handling.
- PV-3 [M] Nozzle schedule: DN/rating, orientation, elevation, reinforcement check per opening; manway selection from standard tables.
- PV-4 [M] Weight & center-of-gravity report (empty, filled, operating, test).
- PV-5 [S] Saddle/support design (Zick method [S17]), skirt base-plate & anchor-bolt design (AISC/ACI [S11]), lug/support local-load check (WRC [S13]).
- PV-6 [S] Internal attachments: tray/cyclone/packing-support loads fed into shell checks.
- PV-7 [C] Water-slinging/vortex-pad checks, demister support, expansion joints (EJMA [S20]).

### FR-TK — Storage tanks pack (API 650)
**Sources:** [S5] for shell/roof/openings/anchorage (§5.6 shell design & annexes — subsection numbering confirmed per edition); wind/seismic inputs from [S10].
- TK-1 [M] Shell course thickness by API 650 method (height of shell, specific gravity, stress, weld joint efficiency, mill tolerance).
- TK-2 [M] Roof type selection (cone, dome, floating) with basic sizing; bottom plate layout.
- TK-3 [M] Nozzle/opening reinforcement per API 650; roof/nozzle load check.
- TK-4 [S] Wind & seismic anchorage (API 650 anchorage provisions), overturning check.
- TK-5 [S] Wind girders, shell openings reinforcement, ladder/platform take-off (quantities).
- TK-6 [C] API 620 low-pressure variant; supplemental plates; seismic zone detailing per current edition annexes.

### FR-HX — Heat exchangers pack (TEMA)
**Sources:** [S6] TEMA R/C/S dimensional & construction rules; [S1] UHX tubesheet rules where ASME governs.
- HX-1 [M] Shell & channel/cover thickness per VIII-1 + TEMA RCB dimensional rules.
- HX-2 [M] Tubesheet thickness check (TEMA method [S6]; UHX [S1] reference flagged), tube layout input (pitch, pattern, passes) with ligament efficiency.
- HX-3 [M] Tube-to-tubesheet joint strength check; expansion-joint allowance note.
- HX-4 [S] Baffle spacing/geometry inputs feeding tube-support checks; nozzle and pass-partition layout.
- HX-5 [S] Expansion/thermal growth check between shell and tubes; differential expansion estimate.
- HX-6 [C] TEMA class selector (R/C/S) with dimension deltas; UHX stress analysis for fixed tubesheets.

### FR-FL — Flanges & nozzles pack
**Sources:** [S3] B16.5/B16.47 rating & dimension tables, B16.20 gaskets; [S1] Appendix 2 for non-standard bolted-flange joints.
- FL-1 [M] Flange rating selection by material class, temperature, pressure (B16.5 tables [S3]) with nearest-upgrade recommendation.
- FL-2 [M] Bolt/gasket selection, bolt-up checks (target torque calc), gasket seating vs operating condition.
- FL-3 [M] Nozzle-size schedule with rating and mating-flange pair.
- FL-4 [S] Non-standard/matching-flange design per VIII-1 App. 2.
- FL-5 [C] B16.47 large-diameter series A/B; RTJ vs spiral-wound comparison; per-code bolt-load optimization.

### FR-PS — Piping & pipe supports pack
**Sources:** [S4] B31.3 paragraphs cited inline; [S12] MSS SP-58 support tables; [S13] local-load methods; [S11] for structural steel.
- PS-1 [M] Straight pipe wall thickness per B31.3 para 304.1.2 (internal pressure), with weld factor, mill tolerance, CA.
- PS-2 [M] Branch/connection reinforcement (B31.3 para 304.3), and component (valve/flange) pressure check.
- PS-3 [M] Pressure–temperature rating verification at design vs operating cases.
- PS-4 [S] Thermal expansion/deflection per B31.3 para 319 (displacement stress range) with guide/anchor span suggestion.
- PS-5 [S] Pipe support selection from MSS SP-58 [S12] tables: hanger sizing, loads, anchor/ guide placement; pipe-shoe local-load check (WRC [S13]).
- PS-6 [C] Simple span calculator (permissible span incl. concentrated load), PSF/occasional loads (B31.3 para 302.3.5).

### FR-CO — Columns & reactors pack
**Sources:** [S1] VIII-1 envelope; [S10] ASCE 7 wind/seismic pressure & seismic base shear; [S11] AISC 360 steel & ACI 318 concrete anchorage.
- CO-1 [M] Tall-shell checks: internal/external pressure [S1], wind and seismic stress combinations with VIII-1 envelope; combined-stress check at skirt transition.
- CO-2 [M] Skirt support design: base plate, anchor bolts (ACI 318 [S11]), gross/fine-anchor load combinations, ring-beam design.
- CO-3 [M] Wind/seismic moment calculation from ASCE 7 [S10] pressure profiles with user height/location/exposure inputs.
- CO-4 [S] Tray/packing support ring & davit loads; ladder/distributor loads as concentrated cases.
- CO-5 [S] Lateral deflection/whip limits at top; vibration screening for internals.
- CO-6 [C] Rotor/reactor internals-specific checks; seismic passive-equipment factors.

### FR-PU — Pumps pack (NEW)
**Scope statement:** selection + mechanical verification + datasheet + GA drawing. Impeller hydraulic design and detailed rotordynamics are out of scope (§8).

**Sources:** [S7] API 610/ISO 13709 (type classes, POR/AOR, shaft deflection, bearing life, nozzle loads, vibration limits, material classes, casing test); [S8] API 682 (seal categories, arrangements, flush plans); [S9] ANSI/HI (NPSH margin, viscosity correction); [S18] ASME B73.1 / ISO 5199 / ISO 2858 (chemical-pump equivalence); [S16] NEMA MG-1 (motor margins); [S14] NACE MR0175/ISO 15156 (sour service); [S1] for custom-casing thickness.

- PU-1 [M] **Duty-point input form:** flow Q, head H, fluid density/viscosity/temperature, NPSH available, speed (or auto), suction conditions, system static head & friction estimate.
- PU-2 [M] **Pump type guidance:** specific speed Ns and suction specific speed Nss computed → recommend radial/mixed-flow/axial and API 610 type class (OH1–OH6, BB1–BB5, VS1–VS7) [S7] or ASME B73.1 / ISO 5199 / ISO 2858 equivalent [S18].
- PU-3 [M] **Selection from catalogue:** match duty point against loaded curve database; rank candidates by efficiency margin; report BEP, %BEP of operating point.
- PU-4 [M] **Operating-region check:** verify operating point lies within API 610 [S7] *preferred* and *allowable* operating regions (POR/AOR); warn with specific remedy (trim, different model, VFD).
- PU-5 [M] **NPSH check:** NPSHa ≥ NPSH3 + required margin per ANSI/HI 9.6.1 [S9]; report margin; flag cavitation risk and suggest remedies.
- PU-6 [M] **Power & driver sizing:** hydraulic power → absorbed power → required NPSH; motor/driver rating with specific-gravity and API 610 [S7] / NEMA MG-1 [S16] margins; current/amp check.
- PU-7 [M] **Casing pressure design:** MAWP determination and casing wall-thickness verification for custom/replace casings using ASME VIII-1 method [S1]; casing hydrostatic test pressure per API 610 [S7].
- PU-8 [M] **Shaft check:** torque + bending from radial/thrust loads → combined stress; **deflection at seal chamber ≤ API 610 [S7] limit (0.05 mm / 0.002 in)**; report safety factor.
- PU-9 [M] **Bearing life:** L10h computed per ISO 281 [S19] method for radial and thrust bearings against the API 610 [S7] minimum required life at rated continuous conditions.
- PU-10 [M] **Mechanical seal selection per API 682 [S8]:** category, arrangement (1/2/3), seal faces vs fluid/temperature, secondary containment; recommend flush/auxiliary plan (e.g. Plan 11/21/23/32/52/53/54); output seal datasheet.
- PU-11 [M] **Piping nozzle-load check:** entered or imported suction/discharge forces & moments checked against API 610 [S7] allowable nozzle loads; report pass/fail per nozzle.
- PU-12 [M] **Materials:** API 610 [S7] material-class selection (S-6, S-8, C-6, A-7, A-8 …) vs fluid + temperature; corrosion/erosion allowance; hardness/galvanic notes for sour service (NACE MR0175/ISO 15156 [S14] flagged).
- PU-13 [M] **Vibration limits:** computed/declared vibration velocity checked against API 610 [S7] limits; report allowable range.
- PU-14 [M] **Datasheet output:** completed API 610-style pump data sheet (PDF) populated from all inputs and results.
- PU-15 [M] **GA drawing:** pump + driver + baseplate assembly in 2D — elevation & plan, nozzle orientation & elevations, tag block, key dimensions, foundation/anchor-bolt pattern.
- PU-16 [S] **Curve overlay view:** pump curve + system curve + operating point + POR/AOR shading + efficiency/power/NPSH curves; export as image for reports.
- PU-17 [S] **Affinity laws:** trim diameter and/or speed change to move the operating point; recheck all PU-4..PU-6 checks automatically after change.
- PU-18 [S] **Critical-speed screening:** first lateral critical vs max continuous speed separation-margin screening (rule-of-thumb level, flagged "screening only — detailed rotordynamic analysis out of scope").
- PU-19 [S] **System NPSH calculator:** suction-line friction + static lift → NPSHa, feeding PU-5.
- PU-20 [S] **Baseplate/foundation:** baseplate layout, anchor-bolt sizing, grout note, motor-pump alignment tolerances as drawing notes.
- PU-21 [C] **Positive-displacement pump mini-pack:** gear/screw/lobe duty → displacement, slip, power, relief-valve sizing.
- PU-22 [C] **Curve import:** load vendor PDF/image curves (digitizer) into the catalogue.
- PU-23 [C] **Parallel/series pump banks:** combined system curve, NPSH interaction, start/stop sequencing notes.

### FR-DR — 2D drawing generation
**Sources:** [S15] for dimensioning & drawing conventions (ASME Y14.5 / ISO 128); layout templates are our own.
- DR-1 [M] Auto-generate a 2D drawing per equipment item: orthographic views (elevation/plan/section), dimensions, centerlines, section hatching, weld symbols (simplified), nozzle callouts.
- DR-2 [M] Drawing annotation layer: key results auto-placed (MAWP, test pressure, corrosion allowance, design conditions).
- DR-3 [M] Title block: project, tag, rev, scale, units, drawing number, date, drawn/checked fields.
- DR-4 [M] Export **DXF** (editable in AutoCAD/LibreCAD) and **PDF** (print-ready).
- DR-5 [M] Consistent layer scheme (geometry, dimensions, annotation, hatching) with named layers per convention.
- DR-6 [S] Template layer: company sheet sizes (A0–A4), title-block customization, hatching patterns.
- DR-7 [S] Dimension-driven re-layout: changing an input re-generates the drawing without manual repositioning.
- DR-8 [C] Auto dimension-chain optimization, isometric hook-up views, DXF round-trip import of edited drawings.

### FR-3D — 3D preview
- 3D-1 [M] Simple interactive 3D preview (orbit/pan/zoom) generated from the same parameters as the 2D drawing: shells, heads, nozzles, supports, pump+driver+baseplate.
- 3D-2 [M] Live update on parameter change (regeneration <2 s typical).
- 3D-3 [S] Section-plane cutting, component show/hide, pick-a-component to highlight its inputs.
- 3D-4 [S] Export STEP/STL for downstream CAD/3D printing.
- 3D-5 [C] Interference/clash check between nozzles, internals, and supports.

### FR-RP — Reporting
- RP-1 [M] One-click PDF calculation report per calculation **and** per equipment item.
- RP-2 [M] Report contains: inputs with units, material properties used, formula as published, formula with substituted values, result, code clause reference, pass/fail, governing load case, notes/assumptions, standard edition.
- RP-3 [M] Summary sheet: equipment data, overall verdict, list of checks with pass/fail and margins.
- RP-4 [S] Hyperlinked contents; appendix for material certificates/notes.
- RP-5 [C] Export report data as JSON/CSV for external document systems.

### FR-EXT — Export & interop
- EXT-1 [M] Export DXF, PDF, PNG (preview), CSV (results), JSON (full project).
- EXT-2 [S] Export to STEP (via 3D), export datasheets as fillable PDF.
- EXT-3 [C] Headless CLI (`pemds calc project.json`), Python API for pipeline use, P&ID/ERP tag integration.

### FR-VAL — Verification & QA
**Sources:** verification benchmarks from open sources & hand-checks (§10.3); no benchmark text is copied into the product.
- VAL-1 [M] Golden test-case suite: each calculation verified against published worked examples and hand-checked benchmarks (§10.3); regression suite runs on every change.
- VAL-2 [M] Calculation status indicator in GUI: "verified" vs "experimental/unverified" per check.
- VAL-3 [S] Property-based tests (monotonicity: thickness ↑ with pressure, etc.) and unit round-trip tests.
- VAL-4 [S] Known-issue/errata register per code edition, visible in reports.
- VAL-5 [C] Third-party validation campaign against commercial tool outputs.

### FR-GUI — Application shell
- GUI-1 [M] Project explorer (left), input forms (center), results panel (right), drawing/3D tabs (bottom/dockable).
- GUI-2 [M] Status bar: overall pass/fail, governing case, unit system, code editions in force.
- GUI-3 [M] Error/warning presentation with jump-to-field navigation.
- GUI-4 [S] Keyboard-driven workflow, command palette, saved workspace layouts.
- GUI-5 [C] Dark mode.

---

## 5. Data model (entity sketch)

```
Project ─┬─ EquipmentItem(type: vessel|tank|hx|column|flange|pipe|pump)
         │    ├─ Component (shell course, head, nozzle, saddle, pump casing, shaft, seal…)
         │    ├─ Material (ref → DB, with service overrides)
         │    ├─ Fluid/DesignCase (ref → Component in FR-CC, or manual: P, T, density, viscosity, corrosion allowance…)
         │    ├─ LoadCase[] (operating, unused, test, wind, seismic…)
         │    ├─ Calculation[] (type, code ref+edition, inputs, ResultTree)
         │    ├─ Drawing[] (type: GA/assembly/section, generated revision)
         │    └─ Report[] (PDF snapshot, revision, sign-off state)
         ├─ Datasheet[] (pump API-610 style, seal API-682 style…)
         └─ RevisionLog (input diffs, timestamps, author)
```

`Result` object: `{symbol, value, unit, formula, substitutions, clause_ref, inputs_used, verdict, margin, governing_case}`.

`Component` object (FR-CC): `{name, synonyms, cas, formula, mw, property_correlations[], provenance{source, licence, correlation, version}, custom_flag}`.

---

## 6. Non-functional requirements

- **NFR-1 Performance:** live recalc of one equipment item < 100 ms; 3D regeneration < 2 s; report generation < 3 s.
- **NFR-2 Determinism:** same inputs + same data edition ⇒ bit-identical results.
- **NFR-3 Units:** zero silent unit errors; all inputs carry units; internal SI; round-trip tests.
- **NFR-4 Precision:** float64; documented rounding only at display; no cumulative rounding in chains.
- **NFR-5 Auditability:** every reported number traceable (RP-2) — this is the product's core value.
- **NFR-6 Data safety:** autosave ≥ 60 s, crash recovery, JSON export of everything.
- **NFR-7 Extensibility:** new equipment pack = new package implementing the pack interface; no core edits.
- **NFR-8 Offline-first:** runs fully offline (code tables are local data).
- **NFR-9 Platform:** Windows primary (macOS/Linux best-effort); Python 3.12+.
- **NFR-10 Test coverage:** ≥ 90% on calculation modules; 100% of [M] checks have golden tests.
- **NFR-11 Accessibility/usability:** every input has a label, unit, and help text; no undocumented magic numbers.

---

## 7. Phasing

### 7.1 Philosophy
"All equipment families in v1" is honored as **breadth-first**: a *thin but complete vertical slice* per family (core thickness/selection check + one drawing + report), then depth. Depth grows per family in v1.x while the architecture is fixed on day one.

### 7.2 Phase map
| Phase | Contents |
|---|---|
| **P0 (v1 core)** | Units, project mgmt, validation, materials DB skeleton, **chemical component DB core (CC-1…CC-5, CC-10)**, VIII-1 core calcs, calc/report/DXF engines, GUI shell, 3D preview, verification harness |
| **P1 (v1 breadth)** | Thin slice in all **7** packs: PV, TK, HX, FL, PS, CO, **PU** — each with its governing checks, one drawing, one report (component DB wired into TK-1, PU-5/PU-19, PV-4 weights via CC-3) |
| **P2 (v1.x depth)** | Supports & anchors (PV-5), flange App.2 (CORE-8), wind/seismic (CO-3/TK-4), pump curve overlay + affinity (PU-16/17), seal datasheet depth (PU-10), TEMA tubesheets (HX-6) |
| **P3 (v2)** | PD pumps, curve import, clash detection, headless CLI/API, third-party validation |

**P1 definition-of-done for the pump pack:** PU-1…PU-15 pass their golden tests, produce an API-610-style datasheet, a GA drawing, and a full calculation report.

### 7.3 What the pump pack deliberately does NOT do (v1)
- ❌ Impeller/casing hydraulic design (CFD-level), blade geometry generation
- ❌ Full rotordynamic / bearing-housing FE analysis (PU-18 is screening only)
- ❌ Vendor-curve licensing (built-in library starts with generic/sample curves; users import their own)
- ❌ P&ID generation
- ❌ Pump *procurement* workflow (RFQ, cost, lead time)

---

## 8. Out of scope (global)

Process simulation & sizing (HYSYS/Aspen territory); 3D detail CAD modelling (the 3D view is a preview, not a modeller); FEA; Div 2 / EN 13445 / PD 5500 / IS 2825 calculation sets (architecture must allow them later); electrical/motor internal design; control-system design; regulatory submission filing.

---

## 9. Risks, assumptions, open questions

| # | Item | Notes |
|---|---|---|
| R-1 | **Scope breadth** | 7 families × full code compliance is multi-year; the breadth-first phasing is the mitigation. Discipline: no family goes deep until P1 is green everywhere. |
| R-2 | **Copyrighted code text** | ASME/API/TEMA standards are copyrighted. §10.2 makes the posture binding: cite clause numbers, implement formulas as own code with provenance, transcribe minimal data with provenance, never ship verbatim standard text/tables; user supplies/holds the standard. Legal review before release. |
| R-3 | **Edition drift** | Code tables change by edition; all data versioned (DB-7) and stamped on reports. |
| R-4 | **Engineering liability** | Reports must state "tool-assisted calculation — qualified engineer responsible" and show verification status (VAL-2). |
| R-5 | **Pump data availability** | Real selection needs vendor curves; start with sample curves + import path (PU-3, PU-22). |
| R-6 | **3D preview cost** | Full parametric 3D for all families is expensive; preview scope kept simple (3D-1) and can lag drawings within v1. |
| R-7 | **Property-data accuracy** | Open-source correlations (CoolProp/WebBook) are engineering estimates; CC-5 compatibility rules are heuristics, not lab-qualified statements. Mitigation: provenance + accuracy flags everywhere (CC-10), warnings not errors, and CC-7 user-override path. |

**Open questions to settle next:**
1. Which code **editions** are authoritative for v1 (VIII-1 2023? API 650 13th? API 610 11th? B31.3 2022? current ASCE 7)?
2. GUI: **desktop (PySide6)** vs **web (NiceGUI)** — affects packaging and the slider/live-update UX.
3. Pump catalogue: sample/generic curves only for v1, or do you have vendor curve data to bundle?
4. Is an imperial-units-first workflow needed for any deliverable (US pump specs tend to be USCS)?
5. Drawing fidelity target: **GA-style sketch** (achievable in v1) vs. near-drafting-quality fabrication drawing (needs DR-7/DR-8 depth)?

---

## 10. Sources & attribution

Reference tags **[S#]** used throughout this document map to the list below. Editions are deliberately not pinned yet — see open question 1; every citation in the product must record `{standard, edition, clause}` at runtime (FR-CIT below, and RP-2).

### 10.1 Source list

| Tag | Source | Used for |
|---|---|---|
| S1 | **ASME BPVC Section VIII, Division 1** — Rules for Construction of Pressure Vessels (ASME) | CORE-2…CORE-8, PV pack, HX tubesheet reference, PU-7 casing |
| S2 | **ASME BPVC Section II, Part D** — Properties (Customary/Metric) | DB-1 allowable stresses, material properties |
| S3 | **ASME B16.5 / B16.47 / B16.20** — Pipe Flanges & Flanged Fittings / Large-Diameter Flanges / Metallic Gaskets (ASME) | FL pack, DB-2 rating tables |
| S4 | **ASME B31.3 / B31.1** — Process Piping / Power Piping (ASME) | PS pack (paras 302.3.5, 304.1.2, 304.3, 319) |
| S5 | **API Standard 650 / 620** — Welded Tanks for Oil Storage / Large, Welded, Low-Pressure Storage Tanks (API) | TK pack |
| S6 | **TEMA Standards** — Tubular Exchanger Manufacturers Association (R/C/S classes) | HX pack |
| S7 | **API Standard 610 / ISO 13709** — Centrifugal Pumps for Petroleum, Petrochemical and Natural Gas Industries (API/ISO) | PU-2…PU-14: type classes, POR/AOR, nozzle loads, vibration, material classes, casing test |
| S8 | **API Standard 682** — Pumps: Shaft Sealing Systems for Centrifugal and Rotary Pumps (API) | PU-10 seal categories/arrangements/flush plans |
| S9 | **ANSI/HI standards** — Hydraulic Institute rotodynamic-pump guidelines (e.g. HI 9.6.1 NPSH margin; exact parts to confirm) | PU-5 NPSH margin, viscosity guidance |
| S10 | **ASCE/SEI 7** — Minimum Design Loads and Associated Criteria for Buildings and Other Structures (ASME/ASCE) | CO-3 wind/seismic, TK-4 inputs |
| S11 | **AISC 360** (Specification for Structural Steel Buildings) & **ACI 318** (Building Code Requirements for Structural Concrete) | PV-5 skirt/anchor, CO-2 ring-beam & anchors |
| S12 | **MSS SP-58** — Pipe Hangers and Supports: Materials, Design, Manufacture, Selection, Application, and Installation (MSS) | PS-5 |
| S13 | **WRC Bulletins 107 & 297** — Local loads at nozzle/shell junctions (Welding Research Council) | CORE-9, PV-5, PS-5 |
| S14 | **NACE MR0175 / ISO 15156** — Materials for use in H2S-containing environments in oil and gas production | PU-12 sour-service notes |
| S15 | **ASME Y14.5** (Dimensioning and Tolerancing) & **ISO 128** (Technical drawings — General principles of presentation) | FR-DR drawing conventions |
| S16 | **NEMA MG-1** — Motors and Generators (NEMA) | PU-6 driver margins |
| S17 | Zick, L.P., *"Stresses in Large Horizontal Cylindrical Pressure Vessels on Two Saddle Supports"*, Welding Journal Research Supplement (1951) — origin of the saddle-support (Zick) method | PV-5 saddle design |
| S18 | **ASME B73.1 / ISO 5199 / ISO 2858** — Chemical process end-suction centrifugal pumps (dimensions/specification) | PU-2 chemical-pump equivalence |
| S19 | **ISO 281** — Rolling bearings: Dynamic load ratings and rating life | PU-9 bearing L10h |
| S20 | **EJMA Standards** — Expansion Joint Manufacturers Association | PV-7 expansion joints |
| S21 | **ASME BPVC Section VIII, Division 2, Part 5** — Design by Analysis (fatigue) | CORE-10 screening only |
| S22 | **CoolProp** — open-source thermophysical property library (fluids, correlations) — MIT licence | CC-1…CC-4 property correlations |
| S23 | **NIST Chemistry WebBook** (SRD) — chemical compound data on the web (US Government work / public domain) | CC-1 identity data (CAS, synonyms, MW), CC-2 reference points |
| S24 | **Published correlation forms** (e.g. Antoine/Wagner vapor-pressure equations, DIPPR-form correlation equations) — equation *forms* are published scientific facts; coefficients always carry their own source | CC-2 evaluation models |

> Clause numbers shown inline in §4 (UG-27, 304.1.2, etc.) are citations to these sources, not reproduced content. Any clause number marked *to confirm* must be verified against the licensed edition during implementation (VAL-1).

### 10.2 Copyright controls (binding for implementation)

ASME/API/TEMA/HI/MSS standards are copyrighted publications. The following rules apply to code, UI, reports, and this document:

1. **Cite, don't reproduce.** Clause/paragraph numbers, formula symbols, and short paraphrases only. Never ship normative standard text, tables, figures, or appendices verbatim in the repo, UI, tooltip text, or PDF reports.
2. **Formulas are implemented as code.** The underlying engineering formulas/facts are implemented from scratch in Python with the `{standard, edition, clause}` citation attached (provenance object, §3.3) — the citation is the attribution; the code is ours.
3. **Numeric data tables get provenance, not wholesale copying.** Allowable-stress tables (S2), flange ratings (S3), and pipe schedules: transcribe only the values actually needed, each row stamped with source + edition + date transcribed (DB-7). Where a table is large and central, prefer public-domain equivalents (§10.3) or make it a user-supplied data file (DB-5) rather than bundling the standard's table.
4. **No endorsement implied.** Do not use ASME/API/TEMA/HI names or logos in branding beyond factual citation of the standard followed.
5. **Reports quote references, not clauses.** RP-2 output shows `ASME VIII-1 (edition), UG-27(c)` plus our own worked substitution — not the clause prose.
6. **Benchmark numbers are facts; benchmark text is not.** Golden tests (VAL-1) may compare numeric results against published examples, but example text/tables are not copied into the suite.
7. **Legal review before release** (tracked as R-2) — this section is engineering posture, not legal advice.

### 10.3 Open/public-domain sources for verification & data

To keep VAL-1 and DB honest without copying copyrighted content:
- **NIST / NBS publications** (US Government works, public domain) — fluid and material property cross-checks for DB-3.
- **NASA Technical Reports** (public domain) — pressure-vessel stress worked examples for golden tests.
- **US NRC / OSHA published documents** (public domain) — regulatory examples and material references.
- **Openly licensed OER / course worked examples** — usable under their license with attribution; check per-source.
- **Original papers** (e.g. Zick 1951 [S17]) — cite the paper, not a textbook's retelling.
- **Independent hand calculations by a qualified engineer** — primary acceptance basis for VAL-1.
- **Commercial tools (VAL-5)** — numeric cross-check only, no content reuse (and separate from open-source license obligations).

### 10.4 New requirement: FR-CIT — Citation integrity

- CIT-1 [M] Every calculation result stores `{standard, edition, clause}` provenance (extends CORE-1/RP-2).
- CIT-2 [M] No module may embed standard text/tables longer than a short quote; lint rule + review checklist enforce §10.2.
- CIT-3 [S] Data-table provenance report: list every DB row's `{source, edition, transcribed-on}` for audit (DB-7 view).
- CIT-4 [S] Citation coverage dashboard: any [M] check lacking a source tag fails CI.

---

*End of document — FR IDs are stable references; cite them in issues and tests (e.g. "PU-8 golden test"). Source tags [S#] resolve via §10.1.*
