#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(realpath "${SCRIPT_DIR}/../..")"
CONFIG_DIR="${SCRIPT_DIR}/config/settings"
VSCODE_DIR="${ROOT_DIR}/.vscode"
C_CPP_SRC="${VSCODE_DIR}/c_cpp_properties.json"
SETTINGS_SRC="${VSCODE_DIR}/settings.json"
BASHRC_TARGET="${HOME}/.bashrc"
BASHRC_OUTPUT="${CONFIG_DIR}/bashrc_add.sh"
MARKER_START="# >>> _raisin_seed >>>"
MARKER_END="# <<< _raisin_seed <<<"
ROOT_RAISIN_SRC="/root/.raisin"
ROOT_RAISIN_SNAPSHOT="${CONFIG_DIR}/.raisin"

mkdir -p "${CONFIG_DIR}"

copy_file() {
  local source_file="$1"
  local destination_file="$2"
  local label="$3"
  if [[ ! -f "${source_file}" ]]; then
    echo "Error: ${label} not found at ${source_file}" >&2
    exit 1
  fi
  cp "${source_file}" "${destination_file}"
  echo "Saved ${label} to ${destination_file}"
}

copy_file "${C_CPP_SRC}" "${CONFIG_DIR}/c_cpp_properties.json" "c_cpp_properties.json"
copy_file "${SETTINGS_SRC}" "${CONFIG_DIR}/settings.json" "settings.json"

if grep -Fq "${MARKER_START}" "${BASHRC_TARGET}" && grep -Fq "${MARKER_END}" "${BASHRC_TARGET}"; then
  awk -v start="${MARKER_START}" -v end="${MARKER_END}" '
    $0 ~ start {capture=1}
    capture {print}
    $0 ~ end {capture=0}
  ' "${BASHRC_TARGET}" > "${BASHRC_OUTPUT}"
  echo "Captured bashrc snippet to ${BASHRC_OUTPUT}"
else
  echo "Warning: marker block not found in ${BASHRC_TARGET}; skipping bashrc export." >&2
  : > "${BASHRC_OUTPUT}"
fi

sync_root_raisin_snapshot() {
  local use_sudo=false
  if [[ -d "${ROOT_RAISIN_SRC}" ]]; then
    :
  elif command -v sudo >/dev/null 2>&1 && sudo test -d "${ROOT_RAISIN_SRC}"; then
    use_sudo=true
  else
    echo "Warning: ${ROOT_RAISIN_SRC} not accessible; skipping root snapshot." >&2
    rm -rf "${ROOT_RAISIN_SNAPSHOT}"
    return
  fi

  mkdir -p "${ROOT_RAISIN_SNAPSHOT}"
  local rsync_cmd=(rsync -a --delete "${ROOT_RAISIN_SRC}/" "${ROOT_RAISIN_SNAPSHOT}/")
  if [[ "${use_sudo}" == true ]]; then
    sudo "${rsync_cmd[@]}"
    sudo chown -R "$(id -u -n)":"$(id -g -n)" "${ROOT_RAISIN_SNAPSHOT}"
  else
    "${rsync_cmd[@]}"
  fi
  echo "Saved ${ROOT_RAISIN_SRC} to ${ROOT_RAISIN_SNAPSHOT}"
}

sync_root_raisin_snapshot
