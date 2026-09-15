# Start KAIROS on Windows

Use the existing Conda environment named `kairos`. Keep the launch scripts next
to `app.py` and `requirements.txt` in this project folder.

## First use or package updates

Double-click **UPDATE_AND_START_KAIROS.bat**. It installs or updates dependencies
inside `kairos`, checks them, and starts the app. Internet access is required.
Wait for the installation to finish; do not close the command window.

## Everyday use

Double-click **START_KAIROS.bat**. This starts the current code in this folder
without installing packages. No manual Conda activation or `.venv` activation is
needed. If your browser does not open, visit http://localhost:8501.

Keep the command window open while using the app. Press Ctrl+C to stop it. Stop
the previous instance before launching another one. Restart after code updates.

Both scripts work from any current directory, including folders containing spaces.
Every Windows launch writes generated schedules and the latest reusable
`room_reservations.csv` to `D:\Projects\kairos_v2_schedules`, outside this
Git checkout. This folder is created automatically and must not be added to
GitHub. After each solve, `room_reservations.csv` is refreshed with that
schedule's physical-room assignments and can be uploaded on the next run.

If automatic Conda discovery fails, open Anaconda Prompt or Miniconda Prompt and run:

```bat
cd /d D:\Projects\KAIROS
UPDATE_AND_START_KAIROS.bat
```

For an unusual Conda installation, set its path before running the script:

```bat
set "KAIROS_CONDA=D:\YourCondaFolder\condabin\conda.bat"
START_KAIROS.bat
```

If Python or pip is missing from the environment, run in Anaconda Prompt:

```bat
conda install -n kairos python=3.12 pip
```

Package updates respect `requirements.txt`, including the project's pinned
Streamlit version. The scripts launch the latest code present in this folder;
they do not download GitHub changes or overwrite local development work.

## Load your data

1. Upload the sections CSV in Courses.
2. Upload the populated rooms CSV in Classrooms.
3. Upload the reservation CSV under Classrooms → Room reservations, then click
   Load reservations.
4. Set instructor/assistant availability and other preferences in Settings.
5. Run scheduling. Reload your CSV inputs when starting a new session.
