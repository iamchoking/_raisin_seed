#!/usr/bin/env bash
set -euo pipefail

# This installer fetches and builds Luxonis depthai-core so CMake can find depthai::core.
# Customize via environment variables:
#   DEPTHAI_VERSION (default: v2.24.0)
#   INSTALL_PREFIX  (default: /usr/local)
#   WORK_DIR        (default: $HOME/.cache/depthai-core)

DEPTHAI_VERSION="${DEPTHAI_VERSION:-v3.2.1}"
INSTALL_PREFIX="${INSTALL_PREFIX:-/usr/local}"
WORK_DIR="${WORK_DIR:-$HOME/.cache/depthai-core}"/"${DEPTHAI_VERSION}"
REPO_URL="https://github.com/luxonis/depthai-core.git"
LOG_PREFIX="[depthai-install]"

log() {
  echo "${LOG_PREFIX} $*"
}

ensure_build_deps() {
  if command -v apt-get >/dev/null 2>&1; then
    log "Installing build prerequisites via apt-get (sudo required)"
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends \
      git build-essential cmake pkg-config libusb-1.0-0-dev libudev-dev curl
  else
    log "apt-get not found; please install git, cmake, build-essential, pkg-config, libusb-1.0-0-dev, libudev-dev manually"
  fi
}

clone_depthai() {
  mkdir -p "${WORK_DIR}"
  if [ -d "${WORK_DIR}/.git" ]; then
    log "Reusing existing checkout at ${WORK_DIR}"
    git -C "${WORK_DIR}" fetch --depth 1 origin "${DEPTHAI_VERSION}"
    git -C "${WORK_DIR}" checkout "${DEPTHAI_VERSION}"
    git -C "${WORK_DIR}" submodule update --init --recursive
  else
    log "Cloning depthai-core ${DEPTHAI_VERSION}"
    git clone --depth 1 --branch "${DEPTHAI_VERSION}" "${REPO_URL}" "${WORK_DIR}"
    git -C "${WORK_DIR}" submodule update --init --recursive
  fi
}

build_and_install() {
  log "Configuring depthai-core with CMAKE_INSTALL_PREFIX=${INSTALL_PREFIX}"
  cmake -S "${WORK_DIR}" -B "${WORK_DIR}/build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="${INSTALL_PREFIX}" \
    -DDEPTHAI_BUILD_EXAMPLES=OFF \
    -DDEPTHAI_BUILD_TESTS=OFF \
    -DBUILD_SHARED_LIBS=ON

  log "Building depthai-core"
  # sudo cmake --build "${WORK_DIR}/build" --target install -j"$(( $(nproc) - 2 ))"
  sudo cmake --build "${WORK_DIR}/build" --target install --parallel 10
}

print_post_instructions() {
  cat <<EOF
${LOG_PREFIX} depthai-core installed to ${INSTALL_PREFIX}
${LOG_PREFIX} Ensure your build can locate it:
  * Default CMake search paths already cover ${INSTALL_PREFIX} on most distros.
  * Otherwise export CMAKE_PREFIX_PATH="${INSTALL_PREFIX}:${CMAKE_PREFIX_PATH:-}" or set depthai_DIR to ${INSTALL_PREFIX}/lib/cmake/depthai.
EOF
}

ensure_build_deps
clone_depthai
build_and_install
print_post_instructions
