<!-- markdownlint-disable MD033 MD041 -->

<p align="center">
  <img src="assets/icon.svg" alt="Kairos logo" width="120" height="120">
</p>

<h1 align="center">KAIROS</h1>

<p align="center">
  <strong>Course Timetabling</strong><br>
  <sub>Course timetabling with practical/lab workloads, teaching-assistant availability, and room reservations.</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python_3.11-0b1220?style=for-the-badge&logo=python&logoColor=3776AB" alt="Python 3.11">
  <img src="https://img.shields.io/badge/OR--Tools_CP--SAT-0b1220?style=for-the-badge&logo=google&logoColor=4285F4" alt="OR-Tools CP-SAT">
  <img src="https://img.shields.io/badge/Streamlit-0b1220?style=for-the-badge&logo=streamlit&logoColor=FF4B4B" alt="Streamlit">
  <img src="https://img.shields.io/badge/Docker-0b1220?style=for-the-badge&logo=docker&logoColor=2496ED" alt="Docker">
  <img src="https://img.shields.io/badge/Google_Cloud_Run-0b1220?style=for-the-badge&logo=googlecloud&logoColor=4285F4" alt="Google Cloud Run">
</p>

---

KAIROS takes a university's raw course and room data and produces a **weekly timetable** where every block has a day, a time, and a room — and no two blocks illegally share any of them. No room is double-booked. No instructor teaches in two places at once. No section exceeds its room's capacity. Every placement is verified by an independent validator after the solver finishes.

It runs two ways: a **web app** for non-technical users and a **command-line solver** for batch runs and benchmarking. The math, rules, and design rationale are in [`MODEL.md`](MODEL.md).

## Changes in this fork

This fork extends KAIROS for scheduling theory, practical, and laboratory teaching
with shared staff and rooms:

- **Separate teaching components:** T, P, and L produce independent sessions.
  A named teaching assistant is assigned to P + L hours only; theory requires
  the instructor alone. A blank assistant name means no assistant is assigned,
  even when practical or laboratory hours are positive. Instructors remain
  required for all components.
- **Name-based staff identity:** instructor and assistant email columns are ignored.
  Consistent names identify the same person across courses and roles, preventing
  simultaneous instructor/assistant assignments.
- **Assistant availability:** separate Unavailable, Avoid, and Preferred settings
  apply to practical and laboratory sessions.
- **Staff-constraints CSV:** Settings can export and import name-based Instructor
  and Assistant Unavailable, Avoid, and Prefer tiers. The CSV is UTF-8 with BOM
  for Excel and supports safe Merge or explicit Replace all. It does not include
  policy settings, course-conflict rules, or room reservations.
- **Room categories and ownership:** classroom, computer laboratory, electronics
  laboratory, and online sessions have distinct eligibility rules. Rooms may
  be shared or assigned to one or more departments.
- **Weekly room reservations:** an optional CSV blocks existing bookings for
  everyone. No physical room can host two courses at once, including courses
  from the same department. Sessions can end at a reservation's start or begin
  at its end.
- **Consecutive course components:** Theory, Practice, and Lab components of a
  section are scheduled consecutively as one sequence, with no other lesson
  inserted between them. Lab hours always use a PC lab; a blank assistant name
  is valid and does not prevent lab scheduling.
- **Private schedule outputs:** each generated schedule also refreshes a
  reusable `room_reservations.csv` containing its physical-room assignments in
  the private schedules directory.
- **Input templates and launchers:** Excel/CSV examples include courses, rooms,
  reservations, and staff constraints. Windows batch files and macOS `.command`
  files run the project in the `kairos` Conda environment and install required packages.
- **Synthetic examples:** bundled inputs use generic role labels and contain no
  real staff or student records. Actual inputs and generated schedules are excluded
  from source control and container builds.

Use `~Students` for reported enrolment or `Section Capacity` for an approved
room-seating requirement; the latter takes precedence when both are present.
At least one must be provided per course row. See [Windows startup](START_ON_WINDOWS.md), [macOS startup](START_ON_MACOS.md), [input schema](INPUT_SCHEMA.md), and
[room reservations](ROOM_RESERVATIONS.md) for usage instructions.

### Public-release privacy check

This fork is intended to be publishable without operational university data.
Its bundled CSV/XLSX examples contain generic names and reserved `example.test`
addresses only. Do not add real course lists, staff constraints, schedules,
screenshots, PDFs, or exported reports to source control.

Before publishing, run:

```powershell
.\tools\Audit-PublicRelease.ps1
.\tools\New-PublicReleaseBranch.ps1 -Push -Remote origin -TargetBranch main
```

The audit rejects common identifiers, real email addresses, PDFs, and
unapproved binary assets. The release script builds a fresh one-commit Git
repository from the audited working tree, so prior Git history is excluded from
the push. It asks for confirmation before any network action. Review all files
before publishing.

---

## ✅ What it does

- **Conflict-free by construction.** Placement-legality rules are enforced during candidate generation; cross-block resource conflicts are enforced in the solver. Violations cannot appear in the output:
  - room capacity respected for every block
  - within its eligible room type, any room of sufficient capacity can be assigned — small classes are not crowded out of the scarce smallest rooms; the room pool scales to the inventory
  - lab blocks pinned to lab/pc/studio rooms; theory blocks excluded from them
  - day window and blackout slots observed
  - no room double-booking, no instructor double-booking, no section self-overlap
  - theory sessions of the same course prefer different days, but may share a day as a soft fallback
  - instructor unavailability slots strictly blocked
- **Optimized, not just valid.** The soft polish phase steers the schedule toward comfort after placement — never at the cost of hard constraints:
  - minimizes cohort idle gaps and reduces late-hour load
  - compacts instructor teaching weeks into fewer days (opt-in)
  - keeps each section in a stable room across its blocks
  - honors per-section minimum spread targets and coordinates parallel sections
  - penalizes user-defined avoid-conflict course pairs
  - spreads multi-session courses across the week
  - balances prime-time access across departments
  - clusters department classes into fewer buildings
  - prefers right-sized rooms over large under-used ones
- **Minimum perturbation.** Upload a previous `schedule_*.json` export as a reference. Assignments that differ in day, start time, or room from the reference receive a soft penalty, steering the new schedule to stay as close as possible to the existing one — useful for incremental updates and rescheduling scenarios.
- **Graded instructor time preferences.** The availability editor supports four tiers per instructor: **unavailable** (hard — never placed in that slot), **avoid** (soft penalty per overlapping hour), **preferred** (soft miss-penalty when a block misses all preferred hours), and **neutral** (default, no cost). Active in both the CP-SAT monolith and the repair soft polish.
- **Works with what you have.** A course list and a classroom inventory are the only required inputs. Cohorts, teaching blocks, and instructor identities are derived automatically.
- **Verified independently.** A validator re-checks placed-block constraints from the raw assignment list — placement count, capacity, lab/room-type legality, fixed first slots, time-window end caps, blackouts, instructor unavailability, and room/instructor/section no-overlap — decoupled from the solver, so encoding bugs in those checked rules cannot pass silently.
- **Exports a ready-to-use result.** A Mon–Fri grid viewable by cohort, room, instructor, or department; `schedule.json` / `schedule.csv` for downstream use; a multi-page PDF.

---

## 🖥️ The app

A single-page flow, bilingual (Turkish / English), usable on a phone in portrait.

**1 · Data** 📥 — Upload a course-list CSV or try the bundled PII-free sample. Review a KPI summary and data-quality warnings. Load a classroom inventory or use the bundled classroom sample.

**2 · Settings** ⚙️ — Configure day window, blackout slots, Saturday toggle, graduate-hour controls, soft-preference presets, and per-instructor availability. Everything is optional — untouched settings fall back to defaults.

**3 · Solve** 🧮 — One click. A five-phase progress display (candidates → construct → repair → soft polish → validate) runs under a fixed 50-minute budget.

**4 · Results** 📊 — Weekly grid, conflict and unschedulable lists, and JSON / CSV / PDF download.

---

## ⚡ Quick start

Requires Python 3.11+.

```bash
.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python -m streamlit run app.py      # http://localhost:8501
```

The web app works without any private data — PII-free sample course and classroom lists ship in `assets/` (loadable from the UI via "Try sample dataset"), or upload your own.

```bash
.venv/bin/python -m pytest -q      # run the test suite
```

For batch runs and benchmarking:

```bash
PYTHONPATH=src .venv/bin/python -m timetabling \
  --courses assets/sample_courses.csv \
  --rooms assets/sample_classrooms.csv \
  --mode A \
  --repair
```

CLI flags: `--courses` is the course-list CSV to optimize. `--rooms` is the classroom inventory; when omitted, the bundled sample inventory is used. `--mode A` generates a new KAIROS schedule.

---

## 🚀 Deployment

KAIROS ships as a single Docker image on **Google Cloud Run**, in the institution's own GCP project, `europe-west1`. The CI deploy keeps **one instance always warm** (`min-instances=1`, `max-instances=1`, session affinity) and is publicly accessible. No PII enters the image — course and classroom data are supplied at runtime.

Every push to `main` triggers [`cloudbuild.yaml`](cloudbuild.yaml). To deploy by hand (mirrors CI):

```bash
gcloud run deploy kairos \
  --source=. \
  --region=europe-west1 \
  --allow-unauthenticated \
  --memory=8Gi \
  --cpu=4 \
  --cpu-boost \
  --timeout=3600 \
  --min-instances=1 \
  --max-instances=1 \
  --concurrency=80 \
  --session-affinity \
  --project=$PROJECT_ID
```

> Keep `--memory 8Gi`. A CP-SAT solve needs at least 4 GiB; the Cloud Run default of 512 MiB kills the container mid-solve.

## Private schedule storage

Every schedule generated by the application is saved locally outside this Git
checkout: on Windows at `D:\Projects\kairos_v2_schedules`, and on macOS at
`~/Projects/kairos_v2_schedules`.
The application does not upload generated schedules to GitHub or cloud storage. This keeps
private schedule data separate from version-controlled source code.

Each run also updates `room_reservations.csv` in that private directory. It contains the
physical-room assignments (`Room, Dept, Day, Start, End`) from the latest schedule and can
be uploaded as a room-reservation input for a subsequent run. Online sessions are excluded.

---

## 📚 Reference

[`MODEL.md`](MODEL.md) — time grid, hard constraints, soft objective, block derivation, design decisions, and benchmarks.

---

<p align="center">
  <strong>KAIROS</strong> · Course Timetabling<br>
  <sub>Every section, placed on a conflict-free weekly grid.</sub>
</p>


Bundled examples are entirely synthetic. Use reserved `example.test` email addresses
for demonstrations. See [SCHEDULING_GUIDE.md](SCHEDULING_GUIDE.md).
