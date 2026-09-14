#!/bin/zsh
# Double-click this file in Finder to start KAIROS on macOS.
# Use UPDATE_AND_START_KAIROS_MAC.command on first use or after dependency changes.

set -u

PROJECT_DIR="${0:A:h}"
ENV_NAME="kairos"
UPDATE_PACKAGES=false

if [[ "${1:-}" == "--update" ]]; then
  UPDATE_PACKAGES=true
fi

cd "$PROJECT_DIR" || exit 1

find_conda() {
  if [[ -n "${KAIROS_CONDA:-}" && -x "$KAIROS_CONDA" ]]; then
    print -r -- "$KAIROS_CONDA"
    return 0
  fi

  if (( $+commands[conda] )); then
    command -v conda
    return 0
  fi

  local candidate
  for candidate in \
    "$HOME/miniconda3/bin/conda" \
    "$HOME/anaconda3/bin/conda" \
    "$HOME/miniforge3/bin/conda" \
    "/opt/homebrew/Caskroom/miniforge/base/bin/conda" \
    "/opt/anaconda3/bin/conda"; do
    if [[ -x "$candidate" ]]; then
      print -r -- "$candidate"
      return 0
    fi
  done
  return 1
}

CONDA="$(find_conda)" || {
  print
  print "Conda was not found. Install Miniconda, Anaconda, or Miniforge, then try again."
  print "For a custom installation, run: KAIROS_CONDA=/full/path/to/conda ./START_KAIROS_MAC.command"
  print
  read "?Press Return to close this window..."
  exit 1
}

if [[ ! -f app.py || ! -f requirements.txt ]]; then
  print "Keep this launcher next to app.py and requirements.txt."
  read "?Press Return to close this window..."
  exit 1
fi

# Open the source folder in Finder. The application itself runs entirely from
# the named Conda environment below.
open "$PROJECT_DIR"

if ! "$CONDA" env list | awk 'NR > 2 {print $1}' | grep -qx "$ENV_NAME"; then
  print "Creating the '$ENV_NAME' Conda environment with Python 3.12..."
  "$CONDA" create --yes --name "$ENV_NAME" python=3.12 pip || {
    print "Could not create the Conda environment."
    read "?Press Return to close this window..."
    exit 1
  }
fi

if [[ "$UPDATE_PACKAGES" == true ]]; then
  print "Upgrading pip and installing project packages in '$ENV_NAME'..."
  "$CONDA" run --no-capture-output --name "$ENV_NAME" python -m pip install --upgrade pip || exit 1
  "$CONDA" run --no-capture-output --name "$ENV_NAME" python -m pip install --upgrade -r requirements.txt || exit 1
  "$CONDA" run --no-capture-output --name "$ENV_NAME" python -m pip check || exit 1
fi

print
print "Starting KAIROS from: $PROJECT_DIR"
print "Conda environment: $ENV_NAME"
print "Keep this Terminal window open. Press Ctrl+C to stop KAIROS."
print "If a browser does not open automatically, visit http://localhost:8501"
print

"$CONDA" run --no-capture-output --name "$ENV_NAME" python -m streamlit run app.py --server.port 8501 --server.address localhost
STATUS=$?

if (( STATUS != 0 )); then
  print
  print "KAIROS did not start. Run UPDATE_AND_START_KAIROS_MAC.command first."
  print "If port 8501 is already in use, stop the other KAIROS window."
  read "?Press Return to close this window..."
fi

exit $STATUS
