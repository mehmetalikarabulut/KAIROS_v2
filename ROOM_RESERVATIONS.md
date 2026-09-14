# Weekly room reservations

Use reservations for existing activities that already occupy a physical room.
A reservation blocks all courses and departments, including the department named
in that row. The Dept field records who occupies the room; it is optional.
Existing room ownership in the Rooms CSV remains a separate eligibility rule.

## Excel and CSV inputs

`assets/kairos_input_template.xlsx` has three sheets with anonymous example data:
Courses, Rooms, and Room Reservations. Replace the examples with your own data.
Save each sheet separately as CSV UTF-8. The application imports CSV files, not
the whole workbook. Neither instructor nor assistant email columns are needed.

Reservation CSV example (`assets/example_room_reservations.csv`):

```csv
Room,Dept,Day,Start,End
ROOM-01,Industrial Engineering,Monday,11:00,13:00
```

- Room must exactly match a physical room in the room inventory. Blank Room rows
  are ignored. Unknown rooms and online rooms are rejected.
- Day accepts Monday–Sunday, Mo–Su, or Turkish weekday names. Bookings repeat weekly.
- Start and End use 24-hour HH:MM on the same day, with End after Start.
  Minute precision is supported for reservations; courses still use hourly slots.
- Multiple rows may reserve the same room on different days or at different times.
  Duplicate or overlapping reservations block the union of those intervals.
- Sessions may end exactly at Start or begin exactly at End. Any overlap is blocked.
- No physical room can host two scheduled courses simultaneously, regardless of
  whether they belong to the same department. External bookings reserve room space
  only; they do not reserve an instructor, assistant, or student group.

## Use in the application

1. Upload your Courses CSV and Rooms CSV as usual.
2. In Classrooms, open Room reservations, choose the reservation CSV, and click
   Load reservations (replace current list).
3. Review the loaded rows, then solve. An invalid reservation upload blocks solving
   until corrected or cleared. Changing the room inventory revalidates reservations
   when solving, so references to removed rooms cannot silently disappear.
4. Use Clear reservations to remove the loaded bookings. Reservations belong to
   the current data session; reload the CSV in a new session. Settings profiles
   do not include these input rows.

The Classrooms page offers downloads of the Excel template and reservation CSV.

## Command line

```powershell
$env:PYTHONPATH = "src"
python -m timetabling --courses assets/example_sections.csv --rooms assets/example_rooms.csv --room-reservations assets/example_room_reservations.csv --mode A --time-limit 10 --out output/reservation-demo
```

CP-SAT, repair, and decomposed solving use the reservation-filtered candidate pool.
Final validation independently flags overlaps as `room_reserved`. Diagnostics
identify when reservations leave a block without any compatible time.
