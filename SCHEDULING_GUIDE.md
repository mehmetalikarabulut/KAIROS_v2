# Institution-neutral customization

Weekly room bookings are supported through a separate reservation CSV. See
[Room reservations](ROOM_RESERVATIONS.md) for the Excel template, upload steps,
time boundaries, and command-line usage.

## Architecture and data flow

CSV headers map to canonical rows in `csv_import`; `ui_input` builds Sections,
Instructors and Rooms. `derive.blocks_from_tpl` creates independent Theory (`#T`),
Practice (`#P`) and Lab (`#L`) blocks, adding numbered suffixes for split sessions.
T never includes P. Existing theory session caps remain; P and L use max_block_len.
Zero total hours retain the legacy credit/default-three-hour theory fallback.

Section stores instructor_ids separately from assistant_ids and assistant_names.
human_ids(kind) deduplicates the union for P/L, and returns only instructors for T.
CP-SAT, repair construction, repair neighborhoods, soft-search moves, decomposed
reservations and final validation use this block-aware resource requirement.
Instructor day/load preferences remain instructor-only; assistants are additional
resources, never replacements. Occupancy has one shared identity namespace.

## Input

Sections required fields: Course Code, Course Name, Dept, Section No, Instructor
Name, T, P, L, Section Capacity. P accepts U, Practice and Uygulama.
Assistant Name is optional. All email columns are ignored and may be omitted.
Blank Assistant Name means no assistant is assigned, even when P or L is positive
or an Assistant Email remains filled. P/L sessions still require the instructor.
Existing Year, Part-time, Room Type, Fixed, ~Students, Min Working Days and Parallel
Policy columns remain supported. Use headers; the original headerless column order
is unchanged, and assistant extensions require headers.

Assistant Name aliases: Assistant, Research Assistant, Research Assistant Name,
Teaching Assistant, Teaching Assistant Name, TA, Araştırma Görevlisi, Arş. Gör.,
Ars. Gor., Asistan. Email aliases: Assistant Email, Research Assistant Email,
Teaching Assistant Email, TA Email, Asistan Email.

Rooms: Room, Capacity, Type; optional Dept (semicolon-separated owner departments).
Rooms remain upload-driven. The supplied example files are illustrative inventory,
not room names hardcoded in the application.

See `assets/example_sections.csv` and `assets/example_rooms.csv` for complete examples
that can be opened in Excel. Save each worksheet as UTF-8 CSV before upload.
For multiple assistants use comma-separated names; quote CSV cells containing commas.

## Identity and availability

The normalized name (lowercase, collapsed whitespace, removed legacy `(S)` marker)
is the identity for both roles. Email values never affect assignment or availability.
Use consistent names across rows; different people need distinct name labels.
Re-enter availability saved in older profiles under email identities using names.

School Settings has separate instructor and Research Assistant availability tabs,
each with the existing hourly Unavailable / Avoid / Prefer grids. Assistants are
discovered from uploaded sections. Session state and Config retain separate tiers.
Profiles retain their existing four-value deserializer API; assistant maps travel
inside the Settings dict and can also be passed explicitly to profile_to_json and
build_config. Old profiles default these maps to empty.

Unavailable removes P/L candidates covering any blocked assistant hour. All
assigned assistants and all instructors must be free. Hard human occupancy prevents
assistant/assistant and instructor/assistant overlaps, including online classes.
Theory ignores assistant availability. Role-specific availability applies in that
role; cross-role occupancy always applies.

Avoid costs w_instr_avoid per occupied avoided assistant-hour. Prefer costs
w_instr_prefer per assistant/block with no hour intersecting that assistant's
preferred slots, matching existing instructor semantics. These are soft penalties
in CP-SAT, repair and soft polish, with no hard preference exclusion. When removing
assistant unavailability restores candidates, exclusions identify the assistants.

Example: mark Assistant A unavailable Tuesday through Friday for all teaching hours.
CS Practice/Lab and EE Lab then occupy distinct Monday slots; their Theory blocks
can use other days. Mark Monday 09:00 Prefer and Monday 16:00 Avoid to guide the
remaining choices. Instructor, room and institutional restrictions still apply.

## Room semantics and compatibility

| Canonical | English | Turkish | Legacy |
|---|---|---|---|
| classroom | Classroom | Derslik | normal |
| pc_lab | PC Lab | PC Lab | pc |
| electronics_lab | Electronics Lab | Elektronik Lab | lab |
| online | Online | Online | studio |

Normalization is centralized in csv_import.normalize_room_type and enforced on Room
construction. studio now means online; architectural studio semantics are removed.
Turkish/English aliases listed in INPUT_SCHEMA are accepted.

The single Room Type column is interpreted per component: online applies to all
blocks. In mixed sections, Theory uses classroom while explicit Room Type applies
to Practice and Lab. A theory-only course can explicitly demand a specialist room.
An explicit classroom demand permits classroom P/L; a lab requiring pc_lab never
uses electronics_lab, and vice versa. With no explicit demand, the legacy behavior
is retained: Lab can use either physical lab category, T/P use classrooms.
Capacity and ownership still apply, including pinned physical lab rooms.

Online uses the first virtual inventory row, or a generated virtual supply token
if none was uploaded. Capacity is retained for display but does not limit virtual
attendance. Virtual supply never consumes room occupancy, room-utilization costs,
or building-change terms. Human, section, institutional and academic scheduling
rules remain active. Explicit physical Room Type never silently becomes online
because inventory is too small. The old automatic oversized-section routing is
retained only for legacy sections without explicit Room Type.

Cohort conflicts remain the existing soft proxy for student conflicts, not a new
hard constraint. Solver navigation, capacity rules and optimization architecture
otherwise remain intact. Old CSVs without assistants work without assistant rules.

## Outputs and manual verification

CSV/JSON retain existing columns and append assistant_id, assistant_name, room_type
and is_online. block_kind distinguishes all three components. Theory exports no
assistant. Results grids and PDF blocks show assistants on P/L. Reports include
component counts, assistant hours and online counts. There is no standalone Excel
export in the existing app; UTF-8 CSV remains Excel-compatible.

1. Start `streamlit run app.py` and upload the two example CSVs.
2. Review Assistant Name and independent T/P/L hours.
3. In School Settings, select Research Assistant availability and restrict Assistant A to
   Monday. Set separate instructor constraints and optional assistant preferences.
4. Solve, inspect P/L assistant labels and distinct Monday occupancy. Theory should
   have no assistant label. Switch English/Turkish and confirm settings labels.
5. Download CSV/JSON/PDF; verify the new fields and component labels.
6. Change both example lab categories to online and use separate instructors and
   assistants; simultaneous virtual blocks should be possible. Reuse the same
   assistant to verify they can no longer overlap.
7. Make an assistant unavailable all week; Review/Solve exclusions should identify
   assistant availability. Remove assistant fields to verify legacy import.

## Scope limits

No automatic assistant allocation, assistant workload limits or separate P/L
assistant pools are implemented. Room Type and assistant lists are section-level
inputs with block-aware interpretation; no per-component input columns are added.
The legacy Plan benchmark lacks component annotations and still treats its sessions
as theory. PDF grids retain their existing compact clipping behavior for very long
labels; CSV/JSON retain full names. School-profile UI remains disabled as before.

## Validation

Tests cover CSV inputs, teaching components, name-based staff identities,
availability, room categories, reservations, exports, and solver consistency.
Some legacy integration tests require external datasets that are not distributed.

## Sample data

Bundled course and room examples use generic role labels. Actual course inputs,
exported schedules, credentials, and local logs must stay outside source control.
Analytics is unconfigured by default. Deployment owners may explicitly set
KAIROS_ANALYTICS_ID and KAIROS_SITE_URL. Required license notices are retained.
