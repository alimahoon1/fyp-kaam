# Manzil Deliverable 2 Report

This directory contains the editable LaTeX source for the FAST-NUCES Deliverable 2 report. The supplied university class and logos remain in `../FYPFast/` and are referenced without modifying the original template.

## Build

From PowerShell in this directory:

```powershell
.\build.ps1
```

The build PDF is written to `build/main.pdf`. Final handoff copies are placed at `../Manzil_Deliverable_2_Report.pdf` and `../output/pdf/Manzil_Deliverable_2_Report.pdf`. The editable submission archive is `../output/source/Manzil_Deliverable_2_Overleaf.zip`.

The build requires MiKTeX with automatic package installation enabled, `pdflatex`, and `bibtex`. Run LaTeX, BibTeX, and two further LaTeX passes if compiling manually.

## Source layout

- `main.tex`: metadata, front matter, package configuration, appendices
- `chapters/`: Chapters 1 through 6
- `references.bib`: verified academic and official sources used by the report
- `REVIEW_NOTES.md`: completeness, sample comparison, validation, and unresolved facts
- `build/`: generated artifacts; `main.pdf` is the compiled report

The interface figures are proposed wireframes, not application screenshots. Implementation claims and experimental results must not be added until supported by repository evidence.
