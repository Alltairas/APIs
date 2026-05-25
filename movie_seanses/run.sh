#!/usr/bin/env bash
# Launch scraper.py inside the venv and log stdout+stderr to YYYY-MM-DD_SCREENINGS.log.
# Pass --notify to also push the result to Telegram via notify.py.
# Any other args are forwarded to scraper.py.
#   ./run.sh -g Science-Fiction --print
#   ./run.sh -g Science-Fiction --notify

set -euo pipefail

PROJECT_DIR="/home/aras/APIs/movie_seanses"
VENV_ACTIVATE="/home/aras/APIs/.venv/bin/activate"
LOG_FILE="${PROJECT_DIR}/$(date +%F)_SCREENINGS.log"

# Split --notify out of the args; everything else goes to scraper.py.
NOTIFY=false
SCRAPER_ARGS=()
for arg in "$@"; do
    if [[ "$arg" == "--notify" ]]; then
        NOTIFY=true
    else
        SCRAPER_ARGS+=("$arg")
    fi
done

cd "${PROJECT_DIR}"
# shellcheck disable=SC1090
source "${VENV_ACTIVATE}"

{
    echo "=== $(date -Iseconds) ==="
    echo "args: $*"
    python scraper.py "${SCRAPER_ARGS[@]}"
    if $NOTIFY; then
        echo "--- telegram ---"
        python notify.py
    fi
    echo "=== exit: $? ==="
} 2>&1 | tee -a "${LOG_FILE}"

deactivate
