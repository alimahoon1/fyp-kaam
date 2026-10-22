# Manzil Deliverable 2 Final Review Notes

## Governing scope

- `Manzil_Deliverable_2_Report_Plan.md` is the content authority, the approved proposal is the authority for project facts, and `FastFyp.cls` remains the formatting foundation.
- The submission contains the required front matter, Chapters 1--6, and bibliography. Internal coverage and open-item appendices were removed from the report and retained in `Manzil_FYP_Context.md`.
- Planned work, design choices, and future measurements remain distinct from implementation or experimental evidence.

## Sample comparison

ParkEase, JobLens, GeoSync, F26-098-1, and the later supplied `main.pdf` report were checked at their title pages, preliminary pages, chapter openings, ordinary body pages, figures, tables, and references. The Manzil cover follows the FAST hierarchy used by the closest samples: paired institutional logos, centred university identity and crest, project title, three student rows, supervisor, Final Year Project label, and fixed submission date. The intentional blank verso after the title is retained. The body uses the template's portrait A4 dimensions, margins, numbered hierarchy, headers, captions, and Times-style typography. Unconfirmed group and certificate information was not invented.

## Corrective passes completed

1. Rebuilt and visually checked the cover and front matter. The Abstract is a single 76-word paragraph and occupies less than half a page. The Executive Summary is stakeholder-oriented and distinct from the Abstract.
2. Forced the Table of Contents to start on its own page, corrected list entries, and fitted the List of Tables on one portrait page. Chapter 1 now follows the sample's exact four-section pattern: Purpose, Intended Audience, Definitions, and Conclusion. Sections 1.3 and 3.1 use the inline definition-list style demonstrated in the supplied reports.
3. Audited numbered headings, paragraph length, body emphasis, bullets, captions, labels, references, and float placement. Normal prose is generally 150--200 words; shorter retained passages introduce equations, algorithms, figures, tables, or lists.
4. Replaced forced body floats with flexible portrait placement. No landscape environment, subcaption construct, distorted image, or forced width-and-height combination remains.
5. Reorganized Chapter 3 to match `main.pdf`: Definitions; Detailed Literature Review; Literature Review Summary Table; and Conclusion. Each technical theme uses numbered Research Overview, Critical Assessment, and Relevance to Manzil subheadings. The 18-study evidence is presented as one continuing portrait longtable with author/year, evaluation setting, reported evidence, and Manzil implications.
6. Corrected technical inconsistencies in occupancy, routing cost, route acceptance, RL state/reward, ambulance-delay definitions, repetition rules, ER ownership, sequence persistence, and corridor recovery.
7. Rendered the complete PDF and inspected every page, then rechecked the cover, contents, text pages, literature tables, wireframes, methodology figures, architecture, class/state diagrams, and bibliography at higher resolution.
8. Reworked Chapter 4 use cases into the supplied FAST tabular format, renamed Section 4.7 to Graphical User Interface, removed the former Requirements Traceability section, and redrew the ER model with explicit keys, ownership, and cardinality.
9. Reorganized Chapter 6 under the requested eight main headings while preserving detailed material in numbered subsections: System Overview, Design Considerations, System Architecture, Architectural Strategies, Domain Model/Class Diagram, Sequence Diagrams, Policies and Tactics, and Conclusion.
10. Set the title and declaration date to 10 October 2026. Added the three supplied signatures as transparent, tightly cropped PNG assets and reformatted the anti-plagiarism page to the supplied reference layout, including an explicitly centered heading, stacked right-aligned Name/Signature pairs, and the lower Authors' Declaration. The completed page was visually verified.
11. Reopened `main.pdf` and aligned the full Chapter 4 sequence with its SRS presentation. Added a screen inventory and navigation diagram before the five proposed wireframes, renamed Data Design to Database Design, and supplied a complete ER view plus two readable relationship-focused ER diagrams and the data dictionary.
12. Expanded Chapter 6 under the requested eight main headings. Added project-specific subsections for four system interaction areas, four design considerations, five architecture topics, seven architectural strategies, three sequence diagrams, and detailed policies and tactics. Short newly added body paragraphs were developed with relevant technical detail rather than padding.
13. Recompiled and visually reviewed the modified pages after both the initial and corrective passes. The second pass corrected ER label spacing and improved paragraph development while preserving portrait layout and project-status boundaries.
14. Reopened the complete Section 4.9 of `main.pdf` and rebuilt Manzil's database diagrams in its Chen-style presentation. The final sequence contains a grouped overview plus enlarged experiment, observation/control, and emergency-routing regions with entity rectangles, attribute ovals, relationship diamonds, underlined keys, foreign-key labels, and cardinalities. Three successive rendered-PDF checks removed connector and attribute collisions before final packaging.

## Validation status

- Final PDF: 97 A4 portrait pages, including the intentional blank title-page verso created by the FAST book layout.
- Final build SHA-256: `E4D948360E3C8FE57B439525CA8F29535F753401BF77FB4F71F47D445BC4053F`.
- No overfull boxes, unresolved citations, unresolved references, duplicate labels, duplicate page destinations, landscape pages, or subcaptions.
- All report figures and tables have one caption, a label, a body reference, and surrounding explanation.
- All 23 bibliography entries are cited. Citation metadata was previously checked through DOI/publisher, proceedings, or official documentation records.
- The MiKTeX log retains narrow-column underfull-box notices and longtable page-splitting diagnostics. Visual inspection confirmed that these do not cross margins or hide content. They are recorded rather than concealed.
- The MiKTeX installation reports that distribution updates have not been checked; this is an environment notice, not a document defect.

## Items requiring team confirmation

1. Whether `F26-104` is the official group identifier.
2. Whether BS(CS) is the correct degree label for all three students.
3. Whether a faculty certificate or approval page is required beyond the supplied template.
4. Exact Lahore road area, map snapshot, network size, and signal count.
5. Final video sources, permissions, annotation volume, detector checkpoint, and tracker configuration.
6. Final DQN architecture, training budget, hyperparameters, selected database, hardware, and measured timing targets.
7. Actual interface screenshots after implementation; the present figures are explicitly proposed wireframes.
