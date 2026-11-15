# Manzil Deliverable 2 / Deliverable III Report

Since 15 Nov 2026 this source is the Deliverable III report (Chapters 1–10, dated 22 Nov 2026). The submitted D2 PDF at `../F26-104_Deliverable-2_Report.pdf` is unchanged, and git history holds the D2 source.

This directory contains the editable LaTeX source for the FAST-NUCES Deliverable 2 report. The supplied university class and logos remain in `../FYPFast/` and are referenced without modifying the original template.

## Build

From PowerShell in this directory:

```powershell
.\build.ps1
```

The build PDF is written to `build/main.pdf` (git-ignored). The submitted copy is kept at `../F26-104_Deliverable-2_Report.pdf`; copy the new build there after recompiling. For Overleaf, upload this directory together with `../FYPFast/`.

If PowerShell stops on MiKTeX's "not checked for updates" notice, run the same pdflatex/bibtex steps from bash. The build requires MiKTeX with automatic package installation enabled, `pdflatex`, and `bibtex`. Run LaTeX, BibTeX, and two further LaTeX passes if compiling manually.

## Source layout

- `main.tex`: metadata, front matter, package configuration, appendices
- `chapters/`: Chapters 1 through 10 (7 implementation and test cases, 8 user manual, 9 results, 10 conclusion and FYP-II plan)
- `figures/results/`: copies of figures from `../results/` and `../models/dqn/` used in Chapters 7–9
- `references.bib`: verified academic and official sources used by the report
- `REVIEW_NOTES.md`: completeness, sample comparison, validation, and unresolved facts
- `build/`: generated on demand by `build.ps1`; not tracked in git

The interface wireframes in Section 4.8 are the FYP-II target; Chapter 8 shows real screenshots of the FYP-I dashboard. Implementation claims and experimental results must not be added until supported by repository evidence.
