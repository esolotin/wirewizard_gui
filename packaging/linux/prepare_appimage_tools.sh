#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

# Download the exact x86_64 AppImage tooling used by CI into the project-local
# build cache. The script never calls sudo or writes outside that cache.

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd -P)"
TOOLS_DIR="${PROJECT_ROOT}/build/linux/tools"

APPIMAGETOOL_VERSION="1.9.1"
APPIMAGETOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-x86_64.AppImage"

APPIMAGE_RUNTIME_REVISION="75849dce7cc37e4319b633df1f116ca895c71a12"
APPIMAGE_RUNTIME_SHA256="1cc49bcf1e2ccd593c379adb17c9f85a36d619088296504de95b1d06215aebbf"
APPIMAGE_RUNTIME_URL="https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64"

APPIMAGETOOL_PATH="${TOOLS_DIR}/appimagetool-${APPIMAGETOOL_VERSION}-x86_64.AppImage"
APPIMAGE_RUNTIME_PATH="${TOOLS_DIR}/type2-runtime-${APPIMAGE_RUNTIME_REVISION}-x86_64"

ACTIVE_TEMP=""

log() {
    printf '[appimage-tools] %s\n' "$*"
}

warn() {
    printf '[appimage-tools] WARNING: %s\n' "$*" >&2
}

die() {
    printf '[appimage-tools] ERROR: %s\n' "$*" >&2
    exit 1
}

cleanup() {
    if [[ -n "${ACTIVE_TEMP}" && -e "${ACTIVE_TEMP}" ]]; then
        rm -f -- "${ACTIVE_TEMP}"
    fi
}
trap cleanup EXIT

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

has_expected_sha256() {
    local path="$1"
    local expected="$2"
    local digest_output=""

    [[ -f "${path}" && ! -L "${path}" ]] || return 1
    digest_output="$(sha256sum -- "${path}")" || return 1
    [[ "${digest_output%% *}" == "${expected}" ]]
}

download_verified() {
    local label="$1"
    local url="$2"
    local expected_sha256="$3"
    local destination="$4"

    if has_expected_sha256 "${destination}" "${expected_sha256}"; then
        log "Using verified cached ${label}: ${destination}"
        return 0
    fi

    [[ ! -d "${destination}" ]] || \
        die "Cache destination is a directory; remove it manually: ${destination}"

    if [[ -e "${destination}" || -L "${destination}" ]]; then
        warn "Cached ${label} failed SHA-256 verification; downloading a replacement"
    else
        log "Downloading ${label}"
    fi

    ACTIVE_TEMP="$(mktemp "${TOOLS_DIR}/.${label}.tmp.XXXXXX")"
    curl \
        --fail \
        --location \
        --show-error \
        --silent \
        --retry 5 \
        --retry-all-errors \
        --retry-delay 2 \
        --connect-timeout 20 \
        --max-time 300 \
        --proto '=https' \
        --tlsv1.2 \
        --output "${ACTIVE_TEMP}" \
        "${url}" || die "Failed to download ${label}"

    if ! has_expected_sha256 "${ACTIVE_TEMP}" "${expected_sha256}"; then
        die "Downloaded ${label} has an unexpected SHA-256 checksum"
    fi

    mv -fT -- "${ACTIVE_TEMP}" "${destination}"
    ACTIVE_TEMP=""
    log "Verified ${label}: ${destination}"
}

main() {
    local machine=""

    require_command uname
    require_command curl
    require_command sha256sum
    require_command mktemp
    require_command mkdir
    require_command mv
    require_command chmod
    require_command rm

    [[ "$(uname -s)" == "Linux" ]] || die "This helper supports Linux only"
    machine="$(uname -m)"
    [[ "${machine}" == "x86_64" ]] || \
        die "This helper supports x86_64 only (detected: ${machine})"

    mkdir -p -- "${TOOLS_DIR}"

    download_verified \
        "appimagetool-${APPIMAGETOOL_VERSION}-x86_64" \
        "${APPIMAGETOOL_URL}" \
        "${APPIMAGETOOL_SHA256}" \
        "${APPIMAGETOOL_PATH}"
    download_verified \
        "type2-runtime-${APPIMAGE_RUNTIME_REVISION}-x86_64" \
        "${APPIMAGE_RUNTIME_URL}" \
        "${APPIMAGE_RUNTIME_SHA256}" \
        "${APPIMAGE_RUNTIME_PATH}"

    chmod 0755 -- "${APPIMAGETOOL_PATH}"

    printf '\nAppImage tools are ready:\n'
    printf '  appimagetool: %s\n' "${APPIMAGETOOL_PATH}"
    printf '  type-2 runtime: %s\n' "${APPIMAGE_RUNTIME_PATH}"
    printf '\nUse them for the build:\n'
    printf '  export APPIMAGETOOL=%q\n' "${APPIMAGETOOL_PATH}"
    printf '  export APPIMAGE_RUNTIME_FILE=%q\n' "${APPIMAGE_RUNTIME_PATH}"
    printf '  export APPIMAGE_EXTRACT_AND_RUN=1\n'
    printf '  bash packaging/linux/build.sh appimage\n'
}

main "$@"
