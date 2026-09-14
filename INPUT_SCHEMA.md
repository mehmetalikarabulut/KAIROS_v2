# KAIROS — Input Data Schema

An optional third input, [weekly room reservations](ROOM_RESERVATIONS.md), blocks
existing room bookings for all departments. Download `assets/kairos_input_template.xlsx`
for Courses, Rooms, and Room Reservations sheets.
Staff constraints are a separate optional CSV (`assets/example_staff_constraints.csv`)
loaded from Settings. It contains personal availability only.

The two tables a user provides to the KAIROS timetabling UI, and how the solver
derives everything else from them. This is the **input contract**: the importer
(`csv_import.py`), the section/room builders (`ui_input.py`), and the data
classes (`model.py`) all conform to it. The optimization model itself is
specified separately in [MODEL.md](MODEL.md); this file is only about *what goes in*.

There are exactly **two independent inputs**, modeled as two tables:

1. **Sections** — the course offerings for one period (uploaded each term).
2. **Rooms** — the classroom inventory (stable; seeded from defaults, edited, or
   imported once).

The `section → room` assignment is the **solver's output**, never an input — so
no room is named on a section row, and no section is named on a room row.

---

## Table 1 — Sections (course list)

One row per section (a single offering of a course). A semicolon-separated Section
identifier such as `1;2;3` expands to three independent class instances; repeated
identities are not scheduled twice. The importer detects a header
row and matches each column by **alias** (TR/EN, case-insensitive), so column order
does not matter — both the clean sample headers (`Course Code`, `Section No`, …) and
a registrar export's headers (`COURSE_CODE`, `SECTION`, `SECT_CAP`, …) are accepted.
A header-less file falls back to a fixed **positional** order (`COURSE_POSITIONAL`
in `csv_import.py`); the table below lists the columns grouped logically, not in that
fallback order.

| Column | Required | Meaning / effect on the solver |
|---|:---:|---|
| `COURSE_CODE` | ✓ | Course code. Source of the **cohort program code** (`ADA 403` → `ADA`). |
| `COURSE_NAME` | ✓ | Display name. |
| `DEPT` | ✓ | **Department/faculty name** (e.g. "Faculty of Econ…") → `Section.department`. **Not** the cohort key (see §Cohort). |
| `SECTION` | ✓ | Section identifier. `"ADA 403_01"` is used **directly** as `section_id`; a bare `"01"` is composed with the code. |
| `LECTURER` | ✓ | Instructor **display name**. Normalized name is the unique scheduling key. |
| `Email` | ignored | Not used for scheduling or availability; may be omitted. |
| `Part-time` | optional | Boolean. Overrides the `(S)` name marker; empty/`false` ⇒ full-time. |
| `T` | ✓ | Theory hours → theory blocks. |
| `P` | ✓ | Practice hours; aliases U, Practice, Uygulama. Independent practice blocks, never added to T. |
| `Assistant Name` | optional | Comma-separated required assistants on Practice/Lab only. Blank means no assistant, even if P/L hours or Assistant Email are filled. |
| `Assistant Email` | ignored | Not used; may be omitted. |
| `L` | ✓ | Laboratory hours, scheduled independently from Theory and Practice. See block-aware room matching below. |
| `Section Capacity` | one of this or `~Students` | **Quota.** Scheduling seating requirement when present. |
| `~Students` | one of this or `Section Capacity` | Reported enrolment and the room-sizing fallback. `Students counts in the section` is also accepted as an import alias. |
| `Room Type` | optional | classroom / pc_lab / electronics_lab / online, including legacy aliases. See block-aware matching below. |
| `Fixed` | optional | Fixed slot for the section's first block (e.g. `"Mo 9"`). |
| `Year` | optional | Overrides the cohort year level. |
| `Min Working Days` | optional | Soft target for how many distinct days this section should occupy. Empty/invalid means no target; unmet days are reported in `unmet_soft` and penalized, never treated as a hard violation. |
| `Parallel Policy` | optional | Course-code scoped soft policy for parallel sections: `same-time`, `spread`, or `lab-after-theory`. Empty/invalid means off. Settings entries for the same course code override the CSV value. |

**Not section columns** (deliberately excluded — they belong to the room table or
are solver output): `ROOM`, `ROOM_CAP`, `SCHEDULE`.

## Table 2 — Rooms (classroom inventory)

| Column | Required | Meaning |
|---|:---:|---|
| `Room` | ✓ | Room name (unique). |
| `Capacity` | ✓ | Seats. |
| `Type` | ✓ | Room category: `classroom / pc_lab / electronics_lab / online`. Legacy values are migrated centrally. |
| `Dept` | optional | **Department ownership** for a room. Semicolon-separated list of department names (e.g. `"Department of Software Engineering;Dept.of Electric&Electronics Engineering"`). When set, only sections whose `DEPT` matches one of the listed values may be assigned to this room. Empty = open to all departments (general pool). |

The user must upload a classroom CSV or load the built-in sample in the Classrooms step before solving.

---

## Shared type vocabulary

Both tables use **classroom / pc_lab / electronics_lab / online**.

| Canonical | Accepted aliases |
|---|---|
| classroom | normal, derslik, sınıf, sinif |
| pc_lab | pc, pc-lab, computer lab, computer laboratory, bilgisayar lab, bilgisayar laboratuvarı |
| electronics_lab | lab, electronics lab, electronic lab, elektronik lab, elektronik laboratuvarı |
| online | studio, virtual, uzaktan, çevrimiçi, cevrimici |

Legacy **studio means online**, without architectural-studio semantics.
Online applies to all section components and uses unlimited virtual supply; an
ONLINE inventory row retains its capacity for administration but does not serialize
courses or limit attendance. Without an uploaded virtual row, a virtual supply token
is generated. Physical occupancy and building changes exclude virtual supply.

For mixed T/P/L sections, Theory uses classroom; explicit Room Type applies to
Practice and Lab. Theory-only sections may explicitly request a specialist category.
Explicit classroom applies to P/L too. Explicit pc_lab and electronics_lab never
substitute for each other. Without demand, legacy Lab accepts either lab category;
Theory and Practice use classroom. Capacity and ownership apply to physical rooms.
An explicit physical demand never silently becomes online when supply is too small.

T, P and L produce independent #T, #P and #L blocks. When a section has more
than one component, they form one hard consecutive sequence in this order:
Theory → Practice → Lab. Their hours are consecutive and no other course can
be inserted between them. A Lab component always uses a `pc_lab`; it does so
even when `Assistant Name` is blank—the instructor remains assigned and no
assistant name is invented.

Assistant aliases: Assistant, Research Assistant, Research Assistant Name, Teaching
Assistant, Teaching Assistant Name, TA, Araştırma Görevlisi, Arş. Gör., Ars. Gor.,
Asistan. Email aliases: Research Assistant Email, Teaching Assistant Email, TA Email,
Asistan Email. Missing assistant fields are valid. Use CSV headers for assistant
extensions; the original positional fallback order remains unchanged.

Assistant and instructor identities use normalized names only. Email columns are ignored.
Use comma-separated names for teams;
all listed assistants are required for P/L, none for Theory. Instructor requirements
remain on all blocks. Equal identities across roles share hard occupancy.
Use consistent names across rows and roles. Different people need distinct name labels.

Research Assistant availability has its own School Settings hourly grids:
Unavailable is hard; Avoid penalizes each occupied marked hour; Prefer penalizes a
P/L block with no preferred-hour intersection. These reuse instructor weights and
are enforced in both solver paths. Profile helpers retain assistant tiers inside
Settings. See [SCHEDULING_GUIDE.md](SCHEDULING_GUIDE.md) for examples and manual checks.

The native staff-constraints CSV schema is `Role,Name,Constraint,Day,Start,End`
with `Instructor`/`Assistant` roles and `Unavailable`, `Avoid`, or `Prefer`
tiers. The importer also reads the supplied legacy personnel format: `TZ` and
`DSÜ` are treated as instructors, and its `Available` windows are converted to
hard unavailability outside their whole teaching hours. Minute boundaries are
preserved conservatively; an hourly class is allowed only when it fits completely
inside an available window.

---

## Derivations & semantics

**Cohort** = `(program code, year level)` — a **soft proxy**, never a hard rule
(see MODEL.md §5.15).
- Program code = the **letter prefix of `COURSE_CODE`** (`ADA 403` → `ADA`) — *not*
  `DEPT`. `DEPT` is faculty-level (it groups many programs), too coarse for a
  cohort; using it would manufacture false conflicts.
- Year level = the first digit of the course number (`ADA 4̲03` → `4`), or the
  `Year` column when present.
- Fallback: if a code cannot be parsed (no letter+digit), the cohort program falls
  back to the (mandatory) `DEPT` so every section still belongs to a cohort.

**Instructor identity.**
- The normalized `LECTURER` name is the key. Email columns are ignored.
- Case and repeated whitespace are normalized; the `(S)` marker is removed.
- Part-time = the `Part-time` boolean when given, else inferred from the `(S)`
  marker in the name. The full-time-only blackout applies if **any** co-instructor
  is full-time.

**Capacity — current implementation.**
- `Section Capacity` (quota) → the scheduling seating requirement; `~Students`
  is used when quota is blank.
- `~Students` → optional fallback/preview field. When `Section Capacity` is
  present, the solver and exported `section_cap` use `Section Capacity`, not a
  separate actual-enrolment value.
- A room's `Capacity` → the room's own size (Table 2).
- Capacity is soft: KAIROS strongly prefers a sufficiently large eligible room,
  but uses the smallest shortfall when no suitable-size room exists. Shortfalls
  appear in exported `unmet_soft` diagnostics, not as hard violations.

**What is *not* in either file** (it lives in the **School Settings** step, not the
upload): institutional policy (day window, weights, blackouts) and per-instructor
availability (keyed by the same normalized-name identity).
