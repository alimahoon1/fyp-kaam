# Deliverable III live demo script (about 4 minutes)

Shown after slide 11 ("Live dashboard") of `presentation_output/Manzil_D3_Presentation.pptx`.
Everything on screen is a live SUMO run; nothing is mocked.

## Before the evaluation (5 minutes)

1. Use the Deliverable III copy of the project (`fyp-kaam-D3`), not the development folder.
2. Run `START_DEMO.ps1` in that folder (or `.venv\Scripts\python -m manzil.api`), wait for "Uvicorn running on http://127.0.0.1:8000".
3. Open http://127.0.0.1:8000 in the browser, zoom so the whole map and the side panel fit.
4. Do one quick practice run, then press **Stop** so the page is idle again.
5. Fallback if anything fails: slide 11 and the screenshots in `results/phase5/` show the same run.

## The demo

| Step | Do | Say |
|---|---|---|
| 1 | In **Run**: controller **DQN**, demand **heavy**, seed **0**, length 3600, speed **10x**. Press **Start run**. | "This is the trained DQN controlling all nine junctions under heavy demand. Each stop line shows its live signal colour; amber and purple roads have queues." |
| 2 | Let it run about 20 seconds. Point at a junction changing phase. | "Every change you see went through the safety filter: 10 s minimum green, 3 s yellow, 2 s all-red." |
| 3 | In **Ambulance**: From **left0A0**, To **C2top2**, **Green corridor** ticked. Press **Dispatch ambulance**. | "The ambulance enters in the south-west and must reach the north-east exit. Its route, in blue, is computed from live travel times." |
| 4 | Click road **B0B1** on the map (on the first route), then **Close road** in **Incident**. | "Now we block a road on its route." |
| 5 | Point at the panel: route version **v2 (closure)**, and the corridor log showing a CANCELLED request. | "The route is recomputed at once, version 2, and priority at the junction that is no longer on the route is cancelled." |
| 6 | Point at the ring around the next junction and its state (safe transition, then green for ambulance). | "The corridor holds only the next two junctions. It finishes yellow and all-red first; it never makes the ambulance run a red light." |
| 7 | Wait for **ARRIVED**. Read the response time and number of stops. | "It arrived; here is its response time against the free-flow time. In our recorded run this scenario took 164 s with 3 stops and 0 seconds at red lights." |
| 8 | Press **Stop**. | "Each run is saved with its configuration, seed and every signal event, so it can be repeated exactly." |

The response time depends on the exact second the ambulance is dispatched, so it will not match 164 s exactly. Do not present the live value as an experimental result; the controlled results are on slides 6 to 8.

## Likely questions

- **Why does the ambulance still stop sometimes?** Vehicles queued in front of it at a green light, or a permissive left turn at the last junction. It is never first in line at a red light at a corridor junction (slide 9).
- **Why not make the whole route green?** It would block cross traffic for minutes; the design limits priority to the next two junctions and 60 s per junction.
- **Is this Lahore?** No, a synthetic 3x3 grid; the Lahore network is the first FYP-II task (slide 14).
- **Why is the DQN unfair to side streets?** It learned to keep long greens; the safety filter's 90 s maximum red bounds it, and a fairness variant is planned.
