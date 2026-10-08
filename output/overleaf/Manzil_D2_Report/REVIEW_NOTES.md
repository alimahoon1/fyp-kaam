# Manzil Deliverable 2 Final Review Notes

## Governing scope

- `Manzil_Deliverable_2_Report_Plan.md` is the content authority; the approved proposal is the authority for project facts.
- `FastFyp.cls` and the supplied FAST/NUCES assets remain the formatting foundation.
- The report contains the six Deliverable 2 chapters, bibliography, coverage appendix, and open-items appendix. It does not add implementation, test-result, or final-outcome chapters that the plan excludes.
- Planned work, design targets, and proposed technologies are distinguished from implemented or measured evidence.

## Sample comparison

ParkEase, JobLens, and GeoSync were reopened and visually checked at their title, preliminary, body, figure, table, and reference pages. ParkEase and GeoSync provided the strongest title-page match: paired university logos, centred university name and crest, project title, three student rows, supervisor, Final Year Project label, and fixed date. The revised Manzil title page follows this hierarchy and omits the unconfirmed group ID and extra department/deliverable labels. All three reference reports use portrait A4 pages and numbered body headings.

## Iterative review passes

1. Rebuilt the title page against the sample PDFs and inspected the rendered comparison.
2. Audited chapter structure, removed body starred headings, shortened the Abstract, separated the stakeholder-oriented Executive Summary, and revised explanatory prose toward 150--200 words.
3. Removed `pdflscape` and the landscape environment. Rebuilt the 18-study literature table as a wrapped portrait long table. Removed body emphasis and label-colon feature bullets. Confirmed one caption per figure/table and no subcaptions.
4. Rendered all pages into contact sheets and inspected the PDF page by page. Corrected a nearly empty chapter-transition page, narrowed an overwide architecture figure, and checked figure/table placement and page density.
5. Rechecked technical boundaries, implementation-status language, matched comparisons, diagram flows, citation use, and bibliography metadata. All 17 DOI-bearing research entries resolve through DOI publishers or Crossref; the remaining research dataset paper and official documentation entries have their cited official records.
6. Recompiled with BibTeX and repeated LaTeX passes, then repeated orientation, warning, reference, citation, and visual checks.

The final verified PDF is 87 portrait A4 pages. The LaTeX log contains no overfull boxes, unresolved citations or references, duplicate-label warnings, or duplicate page destinations. The handoff PDF copies share SHA-256 `C320545BB4AD49DD854DEFC4967AA1A56A9F9B48DAEDBA01FC91887D9A60F957`.

## Paragraph audit

Normal explanatory paragraphs were individually reviewed and developed around one coherent idea, generally within 150--200 words. Short text is retained only where it structurally introduces a list, table, figure, equation, algorithm, or appendix and expanding it would duplicate the adjacent explanation. Table cells, use-case rows, captions, declarations, Abstract, equations, algorithms, and lists are not treated as body paragraphs. Later revisions were re-audited to avoid creating new fragments.

## Coverage and integrity

- Chapter 3 critically reviews 18 peer-reviewed studies; all 23 bibliography entries are cited and no unused entries remain.
- Chapter 4 contains FR-01--FR-20, NFR-01--NFR-12, eight use cases, five explicitly proposed wireframes, an ER model, data dictionary, risk register, and traceability matrix.
- Chapters 5--6 contain the research workflow, perception pipeline, controller/routing/corridor methods, experiment matrix, architecture, domain model, three sequences, corridor states, contracts, ownership, fallback, and testing design.
- Every figure and table has one caption, a label, and surrounding discussion; generated diagrams were checked against the stated one-clock-owner, route-version, safety-filter, and corridor-lifecycle design.
- No results, accuracy values, travel-time improvements, screenshots, deployments, or completed features were fabricated.

## Items for team confirmation

1. Exact Lahore road area, map snapshot, network size, and signal count.
2. Final video sources, permissions, annotation volume, detector checkpoint, and tracker.
3. Final reinforcement-learning algorithm, training budget, and hyperparameters.
4. Final persistence engine, hardware, and measured latency/freshness thresholds.
5. Actual interface screenshots after implementation.
6. Whether a faculty certificate or approval page is required beyond the supplied template.
7. Whether `F26-104` is the official group identifier; it is inferred from a filename and is intentionally not printed on the title page.
