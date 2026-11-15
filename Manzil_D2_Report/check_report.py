"""Consistency checks for the Manzil report source (run after every edit).

Usage, from this folder after a full build into build/:
    ..\\.venv\\Scripts\\python check_report.py

Checks: abstract length (template: 50-125 words), labels that are never referenced,
references without a label, uncited or missing BibTeX keys, headings followed directly by
another heading, chapters without a closing Conclusion section, leftover change wording,
and LaTeX log problems (errors, overfull boxes, undefined or multiply-defined labels).
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
files = [ROOT / "main.tex"] + sorted((ROOT / "chapters").glob("*.tex"))
src = {f.name: f.read_text(encoding="utf-8") for f in files}
text = "\n".join(src.values())
problems = []

m = re.search(r"\\section\*\{Abstract\}(.*?)\\cleardoublepage", src["main.tex"], re.S)
words = len(re.sub(r"\\[a-zA-Z]+|[{}$]", " ", m.group(1)).split()) if m else 0
if not 50 <= words <= 125:
    problems.append(f"abstract has {words} words (template: 50-125)")

labels = re.findall(r"\\label\{([^}#]+)\}", text)
refs = set(re.findall(r"\\(?:ref|eqref|pageref)\{([^}]+)\}", text))
# test-case and use-case labels are created inside macros, so they are passed as arguments
labels += re.findall(r"\\(?:testcase|uctable)\{([^}]+)\}", text)
for lab in labels:
    if lab not in refs and not lab.startswith(("ch:", "eq:", "tab:tc", "tab:uc", "sec:")):
        problems.append(f"label never referenced: {lab}")
for r in sorted(refs - set(labels)):
    problems.append(f"reference without label: {r}")
dups = {lab for lab in labels if labels.count(lab) > 1}
for d in sorted(dups):
    problems.append(f"label defined twice: {d}")

cites = {c.strip() for group in re.findall(r"\\cite\{([^}]+)\}", text) for c in group.split(",")}
keys = re.findall(r"@\w+\{([^,]+),", (ROOT / "references.bib").read_text(encoding="utf-8"))
problems += [f"uncited bib entry: {k}" for k in keys if k not in cites]
problems += [f"cited but not in bib: {c}" for c in sorted(cites - set(keys))]

for name, s in src.items():
    if not name[0].isdigit():
        continue
    lines = [line for line in s.splitlines() if line.strip()]
    for i, line in enumerate(lines[:-1]):
        if re.match(r"\\(chapter|section|subsection|subsubsection)\{", line):
            j = i + 1
            while j < len(lines) and lines[j].startswith("\\label"):
                j += 1
            if j < len(lines) and re.match(r"\\(section|subsection|subsubsection)\{", lines[j]):
                problems.append(f"{name}: heading followed directly by a heading: {line[:60]}")
    sections = re.findall(r"\\section\{([^}]+)\}", s)
    if name not in ("10_conclusion.tex",) and (not sections or sections[-1] != "Conclusion"):
        problems.append(f"{name}: last section is not 'Conclusion'")
    change_words = (
        "Deliverable 2", "deviation from", "Deviation from", "was changed", "in version 2",
    )
    for phrase in change_words:
        if phrase in s:
            problems.append(f"{name}: change wording '{phrase}'")

log = ROOT / "build" / "main.log"
if log.exists():
    for line in log.read_text(encoding="latin-1").splitlines():
        if line.startswith("!") or "Overfull" in line or "undefined" in line or "multiply" in line:
            problems.append(f"log: {line.strip()}")
else:
    problems.append("build/main.log not found: build the report first")

print("\n".join(problems) if problems else "report checks passed")
