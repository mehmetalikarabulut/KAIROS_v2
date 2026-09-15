# Start KAIROS on macOS

Keep both `.command` files next to `app.py` and `requirements.txt` in this
project folder.

## First use or package updates

Double-click **UPDATE_AND_START_KAIROS_MAC.command**. It creates the `kairos`
Conda environment when necessary, installs or upgrades the packages in
`requirements.txt`, opens the project folder in Finder, and starts KAIROS.
Internet access is required for package installation.

## Everyday use

Double-click **START_KAIROS_MAC.command**. It opens the project folder and
starts the current project code using the existing `kairos` Conda environment.
If the browser does not open, visit http://localhost:8501.

Keep the Terminal window open while using KAIROS. Press Ctrl+C in that window
to stop it. Stop an existing KAIROS process before starting another one.

If macOS says the file cannot be opened, right-click it and choose **Open**. If
the files were copied without their executable permission, run this once in
Terminal from the project folder:

```zsh
chmod +x START_KAIROS_MAC.command UPDATE_AND_START_KAIROS_MAC.command
```

The scripts do not pull from GitHub, commit, or push any code or schedule data.
For a non-standard Conda installation, start Terminal with:

```zsh
cd ~/Projects/KAIROS_v2
KAIROS_CONDA=/full/path/to/conda ./UPDATE_AND_START_KAIROS_MAC.command
```
