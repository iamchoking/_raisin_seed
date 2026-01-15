#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(realpath "${SCRIPT_DIR}/../..")"
CONFIG_DIR="${SCRIPT_DIR}/config/settings"
VSCODE_DIR="${ROOT_DIR}/.vscode"
C_CPP_SRC="${CONFIG_DIR}/c_cpp_properties.json"
SETTINGS_SRC="${CONFIG_DIR}/settings.json"
BASHRC_SNIPPET="${CONFIG_DIR}/bashrc_add.sh"
BASHRC_TARGET="${HOME}/.bashrc"
MARKER_START="# >>> _raisin_seed >>>"
MARKER_END="# <<< _raisin_seed <<<"
ROOT_RAISIN_SNAPSHOT="${CONFIG_DIR}/.raisin"
ROOT_RAISIN_TARGET="/root/.raisin"

mkdir -p "${VSCODE_DIR}"

restore_file() {
  local source_file="$1"
  local destination_file="$2"
  local label="$3"
  if [[ ! -f "${source_file}" ]]; then
    echo "Error: stored ${label} missing at ${source_file}" >&2
    exit 1
  fi
  cp "${source_file}" "${destination_file}"
  echo "Restored ${label} to ${destination_file}"
}

restore_file "${C_CPP_SRC}" "${VSCODE_DIR}/c_cpp_properties.json" "c_cpp_properties.json"
restore_file "${SETTINGS_SRC}" "${VSCODE_DIR}/settings.json" "settings.json"

apply_bashrc_snippet() {
  if [[ ! -s "${BASHRC_SNIPPET}" ]]; then
    echo "Warning: bashrc snippet missing or empty at ${BASHRC_SNIPPET}; skipping." >&2
    return
  fi
  local tmp_file
  tmp_file="$(mktemp)"
  if [[ -f "${BASHRC_TARGET}" ]]; then
    awk -v start="${MARKER_START}" -v end="${MARKER_END}" '
      $0 ~ start {skip=1; next}
      $0 ~ end {skip=0; next}
      !skip {print}
    ' "${BASHRC_TARGET}" > "${tmp_file}"
  else
    : > "${tmp_file}"
  fi
  cat "${BASHRC_SNIPPET}" >> "${tmp_file}"
  mv "${tmp_file}" "${BASHRC_TARGET}"
  echo "Updated ${BASHRC_TARGET} with raisin_seed snippet"
}

apply_bashrc_snippet

restore_root_raisin() {
  if [[ ! -d "${ROOT_RAISIN_SNAPSHOT}" ]]; then
    echo "Warning: snapshot ${ROOT_RAISIN_SNAPSHOT} missing; skipping /root/.raisin restore." >&2
    return
  fi

  local rsync_cmd=(rsync -a --delete "${ROOT_RAISIN_SNAPSHOT}/" "${ROOT_RAISIN_TARGET}/")
  if [[ $(id -u) -eq 0 ]]; then
    mkdir -p "${ROOT_RAISIN_TARGET}"
    "${rsync_cmd[@]}"
  else
    if ! command -v sudo >/dev/null 2>&1; then
      echo "Error: need sudo to write ${ROOT_RAISIN_TARGET}." >&2
      exit 1
    fi
    sudo mkdir -p "${ROOT_RAISIN_TARGET}"
    sudo "${rsync_cmd[@]}"
  fi
  echo "Restored ${ROOT_RAISIN_TARGET} from ${ROOT_RAISIN_SNAPSHOT}"
}

restore_root_raisin
