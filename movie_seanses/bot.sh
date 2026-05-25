#!/usr/bin/env bash
# Launch the Telegram bot (long polling) inside the venv.
# Stdout/stderr go to the terminal AND get appended to bot.log.
# Ctrl+C stops it cleanly.

set -euo pipefail

PROJECT_DIR="/home/aras/APIs/movie_seanses"
VENV_ACTIVATE="/home/aras/APIs/.venv/bin/activate"
LOG_FILE="${PROJECT_DIR}/bot.log"

cd "${PROJECT_DIR}"

# shellcheck disable=SC1090
source "${VENV_ACTIVATE}"

echo "=== bot start $(date -Iseconds) ===" | tee -a "${LOG_FILE}"
python -u bot.py 2>&1 | tee -a "${LOG_FILE}"
EXIT=$?
echo "=== bot stop $(date -Iseconds) exit=${EXIT} ===" | tee -a "${LOG_FILE}"

deactivate
exit "${EXIT}"
