#!/usr/bin/env bash

set -Eeuo pipefail
IFS=$'\n\t'

# WireWizardGUI packager for Ubuntu. The script only writes to BUILD_ROOT,
# OUTPUT_DIR and its own temporary directory. It never calls sudo or apt.

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd -P)"

APP_NAME="WireWizardGUI"
APP_ID="wirewizard-gui"
PYINSTALLER_NAME="${PYINSTALLER_NAME:-WireWizardGUI}"
SPEC_FILE="${SPEC_FILE:-${PROJECT_ROOT}/packaging/pyinstaller/WireWizardGUI.spec}"
ENTRY_POINT="${ENTRY_POINT:-${PROJECT_ROOT}/wirewizard_gui/app.py}"
VERSION_CHECKER="${PROJECT_ROOT}/packaging/common/check_version.py"

VERSION="${VERSION:-0.1.0}"
ARCH_INPUT="${ARCH:-}"
TARGETS_ENV="${TARGETS:-portable appimage deb}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PYINSTALLER_VERSION="${PYINSTALLER_VERSION:-6.22.0}"
BUILD_ROOT="${BUILD_ROOT:-${PROJECT_ROOT}/build/linux}"
OUTPUT_DIR="${OUTPUT_DIR:-${PROJECT_ROOT}/dist/linux}"
VENV_DIR_INPUT="${VENV_DIR:-}"
USE_VENV="${USE_VENV:-1}"
INSTALL_DEPS="${INSTALL_DEPS:-1}"
OVERWRITE="${OVERWRITE:-0}"
GRAPHVIZ_MODE="${GRAPHVIZ_MODE:-auto}"
INPUT_GRAPHVIZ_ROOT="${WW_GRAPHVIZ_ROOT:-}"
APPIMAGETOOL="${APPIMAGETOOL:-appimagetool}"
APPIMAGE_RUNTIME_FILE="${APPIMAGE_RUNTIME_FILE:-}"
PIP_CONSTRAINT="${PIP_CONSTRAINT:-}"

usage() {
    cat <<'EOF'
Build WireWizardGUI packages for Ubuntu without changing the host system.

Usage:
  packaging/linux/build.sh [portable] [appdir] [appimage] [deb]
  packaging/linux/build.sh all

With no positional targets, TARGETS is used (default: portable appimage deb).
The appimage target always publishes an AppDir. If appimagetool is not found,
AppDir is kept and only the final .AppImage conversion is skipped.

Important environment variables:
  VERSION=0.1.0             Artifact and Debian package version.
  ARCH=amd64                amd64/x86_64 or arm64/aarch64; no cross-builds.
                            PySide6 6.11.1 requires glibc 2.39+ on arm64
                            (Ubuntu 24.04+); x86_64 supports Ubuntu 22.04+.
  OUTPUT_DIR=...            Artifact directory (default: dist/linux).
  BUILD_ROOT=...            Build cache directory (default: build/linux).
  PYTHON_BIN=python3        Python used for the private build environment.
  USE_VENV=1               Set to 0 to use PYTHON_BIN directly.
  INSTALL_DEPS=1           Install requirements and pinned PyInstaller locally.
  PIP_CONSTRAINT=...        Optional fully pinned pip constraints file.
  OVERWRITE=1              Replace same-version artifacts.
  APPIMAGETOOL=/path/...   Explicit appimagetool path.
  APPIMAGE_RUNTIME_FILE=...  Optional pinned type-2 runtime passed to
                            appimagetool via --runtime-file.

Graphviz policy:
  GRAPHVIZ_MODE=auto       For portable/AppDir, stage the installed Ubuntu
                           Graphviz runtime using dpkg-query (default).
  GRAPHVIZ_MODE=bundle     Like auto; makes the self-contained intent explicit.
  GRAPHVIZ_MODE=system     Do not bundle it. Portable outputs then require the
                           host graphviz package and are not self-contained.
  WW_GRAPHVIZ_ROOT=/path   Use an already staged redistributable Graphviz tree.
                           It must contain bin/dot (or usr/bin/dot), plugins,
                           shared libraries and the applicable license files.

The .deb never embeds Graphviz and declares Depends: graphviz. For repeatable
results, build on the oldest supported Ubuntu, set SOURCE_DATE_EPOCH and pass a
fully pinned PIP_CONSTRAINT file.
EOF
}

log() {
    printf '[linux-build] %s\n' "$*"
}

warn() {
    printf '[linux-build] WARNING: %s\n' "$*" >&2
}

die() {
    printf '[linux-build] ERROR: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

is_enabled() {
    [[ "$1" == "1" ]]
}

declare -a TARGET_LIST=()
if (($# > 0)); then
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
    esac
    TARGET_LIST=("$@")
else
    IFS=" " read -r -a TARGET_LIST <<<"${TARGETS_ENV}"
fi

[[ "${VERSION}" =~ ^[0-9]+([.][0-9]+){1,3}([+~.-][0-9A-Za-z.+~-]+)?$ ]] || \
    die "Invalid VERSION '${VERSION}'. Example: 1.2.3 or 1.2.3~rc1"

case "${GRAPHVIZ_MODE}" in
    auto|bundle|system) ;;
    *) die "GRAPHVIZ_MODE must be auto, bundle, or system" ;;
esac

for flag_name in USE_VENV INSTALL_DEPS OVERWRITE; do
    flag_value="${!flag_name}"
    [[ "${flag_value}" == "0" || "${flag_value}" == "1" ]] || \
        die "${flag_name} must be 0 or 1"
done

declare -A REQUESTED=()
for target in "${TARGET_LIST[@]}"; do
    case "${target}" in
        all)
            REQUESTED[portable]=1
            REQUESTED[appdir]=1
            REQUESTED[appimage]=1
            REQUESTED[deb]=1
            ;;
        portable|appdir|appimage|deb)
            REQUESTED["${target}"]=1
            ;;
        *) die "Unknown target '${target}'" ;;
    esac
done
((${#REQUESTED[@]} > 0)) || die "No build targets selected"

if [[ -n "${REQUESTED[appimage]:-}" ]]; then
    REQUESTED[appdir]=1
fi

[[ "$(uname -s)" == "Linux" ]] || die "Linux packages must be built on Linux"

host_machine="$(uname -m)"
case "${host_machine}" in
    x86_64|amd64)
        HOST_DEB_ARCH="amd64"
        HOST_APPIMAGE_ARCH="x86_64"
        ;;
    aarch64|arm64)
        HOST_DEB_ARCH="arm64"
        HOST_APPIMAGE_ARCH="aarch64"
        ;;
    *) die "Unsupported build host architecture: ${host_machine}" ;;
esac

case "${ARCH_INPUT:-${HOST_DEB_ARCH}}" in
    amd64|x86_64)
        DEB_ARCH="amd64"
        APPIMAGE_ARCH="x86_64"
        ;;
    arm64|aarch64)
        DEB_ARCH="arm64"
        APPIMAGE_ARCH="aarch64"
        ;;
    *) die "Unsupported ARCH '${ARCH_INPUT}' (use amd64/x86_64 or arm64/aarch64)" ;;
esac

[[ "${DEB_ARCH}" == "${HOST_DEB_ARCH}" ]] || \
    die "PyInstaller cannot cross-build: host is ${HOST_DEB_ARCH}, requested ${DEB_ARCH}"

[[ -f "${SPEC_FILE}" ]] || die "PyInstaller spec not found: ${SPEC_FILE}"
[[ -f "${ENTRY_POINT}" ]] || die "Application entry point not found: ${ENTRY_POINT}"
[[ -f "${VERSION_CHECKER}" ]] || die "Version checker not found: ${VERSION_CHECKER}"
[[ -f "${PROJECT_ROOT}/requirements.txt" ]] || die "requirements.txt not found"
[[ -f "${PROJECT_ROOT}/requirements-build.txt" ]] || die "requirements-build.txt not found"
[[ -f "${PROJECT_ROOT}/LICENSE" ]] || die "LICENSE not found"
[[ -f "${PROJECT_ROOT}/THIRD_PARTY_NOTICES.md" ]] || die "THIRD_PARTY_NOTICES.md not found"

for tool in \
    awk basename chmod cp dirname find gzip install ldd ln mktemp mv readlink rm sed \
    sort tar touch uname; do
    require_command "${tool}"
done
if [[ -n "${REQUESTED[deb]:-}" ]]; then
    require_command dpkg-deb
    require_command du
fi

mkdir -p -- "${BUILD_ROOT}" "${OUTPUT_DIR}"
BUILD_ROOT="$(CDPATH= cd -- "${BUILD_ROOT}" && pwd -P)"
OUTPUT_DIR="$(CDPATH= cd -- "${OUTPUT_DIR}" && pwd -P)"
if [[ -n "${VENV_DIR_INPUT}" ]]; then
    mkdir -p -- "${VENV_DIR_INPUT}"
    VENV_DIR="$(CDPATH= cd -- "${VENV_DIR_INPUT}" && pwd -P)"
else
    VENV_DIR="${BUILD_ROOT}/venv"
fi

WORK_DIR="$(mktemp -d "${BUILD_ROOT}/wirewizard-linux.XXXXXXXX")"
cleanup() {
    if [[ -n "${WORK_DIR:-}" && -d "${WORK_DIR}" ]]; then
        case "${WORK_DIR}" in
            "${BUILD_ROOT}"/wirewizard-linux.*) rm -rf -- "${WORK_DIR}" ;;
            *) warn "Refusing to remove unexpected temporary path: ${WORK_DIR}" ;;
        esac
    fi
}
trap cleanup EXIT INT TERM

SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-}"
if [[ -z "${SOURCE_DATE_EPOCH}" ]] && command -v git >/dev/null 2>&1; then
    SOURCE_DATE_EPOCH="$(git -C "${PROJECT_ROOT}" log -1 --format=%ct 2>/dev/null || true)"
fi
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-0}"
[[ "${SOURCE_DATE_EPOCH}" =~ ^[0-9]+$ ]] || die "SOURCE_DATE_EPOCH must be an integer"
export SOURCE_DATE_EPOCH

prepare_python() {
    local installed_pyinstaller python_path
    local -a pip_args

    require_command "${PYTHON_BIN}"
    python_path="$(command -v "${PYTHON_BIN}")"

    if is_enabled "${USE_VENV}"; then
        if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
            log "Creating private build environment: ${VENV_DIR}"
            "${python_path}" -m venv "${VENV_DIR}" || \
                die "Could not create venv (on Ubuntu install python3-venv first)"
        fi
        BUILD_PYTHON="${VENV_DIR}/bin/python"
    else
        BUILD_PYTHON="${python_path}"
    fi

    if is_enabled "${INSTALL_DEPS}"; then
        log "Installing project dependencies into the build environment"
        pip_args=(
            install
            --disable-pip-version-check
            --requirement "${PROJECT_ROOT}/requirements-build.txt"
        )
        if [[ -n "${PIP_CONSTRAINT}" ]]; then
            [[ -f "${PIP_CONSTRAINT}" ]] || die "PIP_CONSTRAINT not found: ${PIP_CONSTRAINT}"
            pip_args+=(--constraint "${PIP_CONSTRAINT}")
        else
            warn "PIP_CONSTRAINT is not set; transitive dependency versions may change"
        fi
        "${BUILD_PYTHON}" -m pip "${pip_args[@]}"
    fi

    "${BUILD_PYTHON}" -c 'import PyInstaller, PySide6, wireviz, yaml' || \
        die "Build environment is incomplete; set INSTALL_DEPS=1 or install PyInstaller, PySide6, WireViz and PyYAML"
    installed_pyinstaller="$("${BUILD_PYTHON}" -c 'import importlib.metadata; print(importlib.metadata.version("PyInstaller"))')"
    [[ "${installed_pyinstaller}" == "${PYINSTALLER_VERSION}" ]] || \
        die "PyInstaller ${installed_pyinstaller} is installed; expected ${PYINSTALLER_VERSION}"
}

copy_tree_entry() {
    local source_path="$1"
    local destination_root="$2"
    local relative_path

    case "${source_path}" in
        /usr/*) relative_path="${source_path#/usr/}" ;;
        /*) relative_path="${source_path#/}" ;;
        *) return 0 ;;
    esac
    mkdir -p -- "${destination_root}/$(dirname -- "${relative_path}")"
    if [[ -L "${source_path}" || -f "${source_path}" ]]; then
        cp -a -- "${source_path}" "${destination_root}/${relative_path}"
    fi
}

copy_runtime_dependency() {
    local source_path="$1"
    local destination_root="$2"
    local relative_path

    case "${source_path}" in
        /usr/*) relative_path="${source_path#/usr/}" ;;
        /*) relative_path="${source_path#/}" ;;
        *) return 0 ;;
    esac
    mkdir -p -- "${destination_root}/$(dirname -- "${relative_path}")"
    # ldd usually reports an SONAME symlink. Dereference it so the staged tree
    # does not contain a dangling link without its versioned target.
    cp -aL -- "${source_path}" "${destination_root}/${relative_path}"
}

is_graphviz_runtime_path() {
    local package_name="$1"
    local source_path="$2"
    local base_name
    base_name="$(basename -- "${source_path}")"

    case "${source_path}" in
        /usr/bin/*)
            [[ "${package_name}" == graphviz* ]]
            ;;
        /usr/lib/*/graphviz/*|/usr/lib/graphviz/*|/usr/share/graphviz/*)
            return 0
            ;;
        /usr/lib/*|/lib/*)
            [[ "${base_name}" =~ ^lib(cdt|cgraph|gvc|gvpr|pathplan|xdot|lab_gamut|gvplugin_).*[.]so([.][0-9]+)*$ ]]
            ;;
        /usr/share/doc/*/copyright)
            case "${package_name}" in
                graphviz*|libcdt*|libcgraph*|libgvc*|libgvplugin*|libgvpr*|libpathplan*|libxdot*|liblab-gamut*) return 0 ;;
                *) return 1 ;;
            esac
            ;;
        *) return 1 ;;
    esac
}

is_core_system_library() {
    case "$(basename -- "$1")" in
        ld-linux*.so*|libc.so*|libdl.so*|libgcc_s.so*|libm.so*|libpthread.so*|librt.so*|libstdc++.so*) return 0 ;;
        *) return 1 ;;
    esac
}

verify_graphviz_bundle() {
    local root="$1"
    local library_path=""
    local plugin_dir=""
    local format
    local candidate

    for candidate in \
        "${root}/lib" "${root}"/lib/* \
        "${root}/lib64" "${root}"/lib64/*; do
        if [[ -d "${candidate}" ]]; then
            library_path="${candidate}${library_path:+:${library_path}}"
        fi
    done
    for candidate in \
        "${root}/lib/graphviz" "${root}"/lib/*/graphviz \
        "${root}/lib64/graphviz" "${root}"/lib64/*/graphviz; do
        if [[ -d "${candidate}" ]]; then
            plugin_dir="${candidate}"
            break
        fi
    done

    for format in svg png; do
        PATH="${root}/bin:${PATH}" \
        LD_LIBRARY_PATH="${library_path}" \
        GVBINDIR="${plugin_dir}" \
            "${root}/bin/dot" -T"${format}" -o /dev/null <<< 'digraph { a -> b }' || \
            die "Staged Graphviz runtime could not render a test ${format} graph"
    done
}

stage_system_graphviz() {
    local destination="$1"
    local dot_path package package_name source_path elf_path dependency plugin_dir config_file
    local -a graphviz_packages=()

    require_command dot
    require_command dpkg-query
    require_command ldd

    dot_path="$(readlink -f -- "$(command -v dot)")"
    [[ -x "${dot_path}" ]] || die "Installed Graphviz dot executable is invalid"
    mkdir -p -- "${destination}"

    while IFS= read -r package; do
        package_name="${package%%:*}"
        case "${package_name}" in
            graphviz|libcdt[0-9]*|libcgraph[0-9]*|libgvc[0-9]*|libgvplugin*|libgvpr[0-9]*|libpathplan[0-9]*|libxdot[0-9]*|liblab-gamut[0-9]*)
                graphviz_packages+=("${package}")
                ;;
        esac
    done < <(dpkg-query -W -f='${binary:Package}\n' 2>/dev/null)
    ((${#graphviz_packages[@]} > 0)) || die "No installed Graphviz Debian packages were found"

    for package in "${graphviz_packages[@]}"; do
        package_name="${package%%:*}"
        while IFS= read -r source_path; do
            if is_graphviz_runtime_path "${package_name}" "${source_path}"; then
                copy_tree_entry "${source_path}" "${destination}"
            fi
        done < <(dpkg-query -L "${package}")
    done

    # Some Graphviz versions generate configN* during package setup, so
    # those files are present at runtime but absent from dpkg-query -L.
    for plugin_dir in /usr/lib/graphviz /usr/lib/*/graphviz; do
        [[ -d "${plugin_dir}" ]] || continue
        for config_file in "${plugin_dir}"/config[0-9]*; do
            [[ -f "${config_file}" ]] || continue
            copy_tree_entry "${config_file}" "${destination}"
        done
    done

    # ldd reports the loaded dependency closure for each ELF. Bundle the
    # non-glibc portion; core libc/C++ runtimes remain host dependencies for
    # AppImage compatibility.
    while IFS= read -r -d '' elf_path; do
        while IFS= read -r dependency; do
            [[ -f "${dependency}" ]] || continue
            is_core_system_library "${dependency}" && continue
            copy_runtime_dependency "${dependency}" "${destination}"
        done < <(
            ldd "${elf_path}" 2>/dev/null | awk '
                /=> \/[^ ]+/ { print $3 }
                /^[[:space:]]*\/[^ ]+[[:space:]]+\(/ { print $1 }
            ' | sort -u
        )
    done < <(find "${destination}/bin" "${destination}/lib" -type f -print0 2>/dev/null)

    [[ -x "${destination}/bin/dot" ]] || \
        die "Automatic Graphviz staging did not produce bin/dot"
    verify_graphviz_bundle "${destination}"
}

normalise_graphviz_root() {
    local source_root="$1"
    local destination="$2"
    local canonical_source

    [[ -d "${source_root}" ]] || die "WW_GRAPHVIZ_ROOT is not a directory: ${source_root}"
    canonical_source="$(CDPATH= cd -- "${source_root}" && pwd -P)"
    mkdir -p -- "${destination}"

    if [[ -x "${canonical_source}/bin/dot" ]]; then
        cp -a -- "${canonical_source}/." "${destination}/"
    elif [[ -x "${canonical_source}/usr/bin/dot" ]]; then
        cp -a -- "${canonical_source}/usr/." "${destination}/"
        if [[ -d "${canonical_source}/licenses" ]]; then
            cp -a -- "${canonical_source}/licenses" "${destination}/licenses"
        fi
    else
        die "WW_GRAPHVIZ_ROOT must contain bin/dot or usr/bin/dot"
    fi

    [[ -x "${destination}/bin/dot" ]] || die "Normalised Graphviz bundle has no executable bin/dot"
    verify_graphviz_bundle "${destination}"
}

needs_portable_runtime=0
if [[ -n "${REQUESTED[portable]:-}" || -n "${REQUESTED[appdir]:-}" ]]; then
    needs_portable_runtime=1
fi

EFFECTIVE_GRAPHVIZ_ROOT=""
if ((needs_portable_runtime)) && [[ "${GRAPHVIZ_MODE}" != "system" ]]; then
    EFFECTIVE_GRAPHVIZ_ROOT="${WORK_DIR}/graphviz-root"
    if [[ -n "${INPUT_GRAPHVIZ_ROOT}" ]]; then
        log "Using Graphviz bundle from WW_GRAPHVIZ_ROOT"
        normalise_graphviz_root "${INPUT_GRAPHVIZ_ROOT}" "${EFFECTIVE_GRAPHVIZ_ROOT}"
    else
        log "Staging the installed Graphviz runtime for portable artifacts"
        stage_system_graphviz "${EFFECTIVE_GRAPHVIZ_ROOT}"
    fi
elif ((needs_portable_runtime)); then
    warn "GRAPHVIZ_MODE=system: portable/AppImage outputs require Graphviz on the target host"
    if [[ -n "${INPUT_GRAPHVIZ_ROOT}" ]]; then
        warn "WW_GRAPHVIZ_ROOT is ignored because GRAPHVIZ_MODE=system"
    fi
fi

prepare_python
log "Checking release version consistency"
"${BUILD_PYTHON}" "${VERSION_CHECKER}" --expected "${VERSION}"

PYI_DIST="${WORK_DIR}/pyinstaller-dist"
PYI_WORK="${WORK_DIR}/pyinstaller-work"
mkdir -p -- "${PYI_DIST}" "${PYI_WORK}"
if [[ -n "${EFFECTIVE_GRAPHVIZ_ROOT}" ]]; then
    export WW_GRAPHVIZ_ROOT="${EFFECTIVE_GRAPHVIZ_ROOT}"
else
    unset WW_GRAPHVIZ_ROOT
fi

log "Building PyInstaller onedir payload"
"${BUILD_PYTHON}" -m PyInstaller \
    --noconfirm \
    --clean \
    --distpath "${PYI_DIST}" \
    --workpath "${PYI_WORK}" \
    "${SPEC_FILE}"

PYI_OUTPUT="${PYI_DIST}/${PYINSTALLER_NAME}"
[[ -d "${PYI_OUTPUT}" ]] || die "PyInstaller output directory not found: ${PYI_OUTPUT}"
[[ -x "${PYI_OUTPUT}/${PYINSTALLER_NAME}" ]] || \
    die "PyInstaller executable not found: ${PYI_OUTPUT}/${PYINSTALLER_NAME}"

# Qt's TIFF image plugin is not used by WireWizardGUI. Current PySide6 wheels
# link it to libtiff.so.5, which is unavailable on Ubuntu 24.04 (libtiff6).
# Removing the optional plugin avoids shipping a known-unloadable binary.
while IFS= read -r -d '' optional_plugin; do
    log "Removing unused Qt TIFF plugin: ${optional_plugin#${PYI_OUTPUT}/}"
    rm -f -- "${optional_plugin}"
done < <(find "${PYI_OUTPUT}" -type f -path '*/plugins/imageformats/libqtiff.so' -print0)

if ((needs_portable_runtime)); then
    qt_xcb_plugin="$(find "${PYI_OUTPUT}" -type f -path '*/plugins/platforms/libqxcb.so' -print -quit)"
    [[ -n "${qt_xcb_plugin}" ]] || die "Qt xcb platform plugin is missing from the portable payload"
    missing_qt_libraries="$(
        LC_ALL=C ldd "${qt_xcb_plugin}" 2>/dev/null |
            awk '/=> not found/ { print $1 }' |
            LC_ALL=C sort -u
    )"
    if [[ -n "${missing_qt_libraries}" ]]; then
        printf '%s\n' "${missing_qt_libraries}" >&2
        die "Qt xcb runtime is incomplete. Install the Ubuntu XCB build prerequisites listed in packaging/README.md and rebuild"
    fi

    required_qt_sonames=(
        libxkbcommon-x11.so.0
        libxcb-cursor.so.0
        libxcb-icccm.so.4
        libxcb-image.so.0
        libxcb-keysyms.so.1
        libxcb-render-util.so.0
        libxcb-shape.so.0
        libxcb-util.so.1
        libxcb-xkb.so.1
    )
    for required_soname in "${required_qt_sonames[@]}"; do
        bundled_library="$(find "${PYI_OUTPUT}" -name "${required_soname}" -print -quit)"
        [[ -n "${bundled_library}" ]] || \
            die "Portable payload does not contain required Qt library ${required_soname}"
    done
fi

make_metadata() {
    local destination="$1"
    {
        printf 'Application: %s\n' "${APP_NAME}"
        printf 'Version: %s\n' "${VERSION}"
        printf 'Debian-Architecture: %s\n' "${DEB_ARCH}"
        printf 'AppImage-Architecture: %s\n' "${APPIMAGE_ARCH}"
        printf 'Source-Date-Epoch: %s\n' "${SOURCE_DATE_EPOCH}"
        printf 'PyInstaller: %s\n' "${PYINSTALLER_VERSION}"
        printf '\nPython packages:\n'
        "${BUILD_PYTHON}" -m pip freeze --all | LC_ALL=C sort
    } >"${destination}"
}

make_payload() {
    local destination="$1"
    local mode="${2:-installed}"

    mkdir -p -- "${destination}/app" "${destination}/licenses"
    cp -a -- "${PYI_OUTPUT}/." "${destination}/app/"
    install -m 0755 "${SCRIPT_DIR}/launcher.sh" "${destination}/WireWizardGUI"
    install -m 0644 "${PROJECT_ROOT}/LICENSE" "${destination}/licenses/LICENSE"
    install -m 0644 "${PROJECT_ROOT}/THIRD_PARTY_NOTICES.md" \
        "${destination}/licenses/THIRD_PARTY_NOTICES.md"
    install -m 0644 "${PROJECT_ROOT}/packaging/licenses/EPL-2.0.txt" \
        "${destination}/licenses/EPL-2.0.txt"
    if [[ "${mode}" == "portable" ]]; then
        touch "${destination}/portable.flag"
    fi
    make_metadata "${destination}/BUILD-METADATA.txt"
}

strip_bundled_graphviz() {
    local payload="$1"
    local candidate
    for candidate in \
        "${payload}/graphviz" \
        "${payload}/app/graphviz" \
        "${payload}/app/_internal/graphviz"; do
        if [[ -d "${candidate}" ]]; then
            rm -rf -- "${candidate}"
        fi
    done
}

prepare_output_file() {
    local destination="$1"
    if [[ -e "${destination}" || -L "${destination}" ]]; then
        if is_enabled "${OVERWRITE}"; then
            [[ -f "${destination}" || -L "${destination}" ]] || \
                die "Refusing to overwrite non-file artifact: ${destination}"
            rm -f -- "${destination}"
        else
            die "Artifact already exists: ${destination} (set OVERWRITE=1 to replace it)"
        fi
    fi
}

publish_output_directory() {
    local source="$1"
    local destination="$2"
    if [[ -e "${destination}" || -L "${destination}" ]]; then
        if is_enabled "${OVERWRITE}"; then
            case "$(basename -- "${destination}")" in
                WireWizardGUI-*.AppDir) rm -rf -- "${destination}" ;;
                *) die "Refusing to replace unexpected directory: ${destination}" ;;
            esac
        else
            die "Artifact already exists: ${destination} (set OVERWRITE=1 to replace it)"
        fi
    fi
    mv -- "${source}" "${destination}"
}

if [[ -n "${REQUESTED[portable]:-}" ]]; then
    portable_name="${APP_NAME}-${VERSION}-linux-${APPIMAGE_ARCH}-portable"
    portable_parent="${WORK_DIR}/portable"
    portable_root="${portable_parent}/${portable_name}"
    portable_output="${OUTPUT_DIR}/${portable_name}.tar.gz"

    log "Creating portable tar.gz"
    make_payload "${portable_root}" portable
    find "${portable_root}" -exec touch -h -d "@${SOURCE_DATE_EPOCH}" {} +
    prepare_output_file "${portable_output}"
    tar \
        --sort=name \
        --mtime="@${SOURCE_DATE_EPOCH}" \
        --owner=0 \
        --group=0 \
        --numeric-owner \
        -C "${portable_parent}" \
        -cf - "${portable_name}" | gzip -n >"${WORK_DIR}/${portable_name}.tar.gz"
    mv -- "${WORK_DIR}/${portable_name}.tar.gz" "${portable_output}"
    tar -tzf "${portable_output}" >/dev/null
fi

APPDIR_OUTPUT=""
if [[ -n "${REQUESTED[appdir]:-}" ]]; then
    appdir_stage="${WORK_DIR}/${APP_NAME}.AppDir"
    appdir_payload="${appdir_stage}/usr/lib/${APP_ID}"
    APPDIR_OUTPUT="${OUTPUT_DIR}/${APP_NAME}-${VERSION}-${APPIMAGE_ARCH}.AppDir"

    log "Creating AppDir"
    make_payload "${appdir_payload}" portable
    install -Dm0755 "${SCRIPT_DIR}/AppRun" "${appdir_stage}/AppRun"
    install -Dm0644 "${SCRIPT_DIR}/${APP_ID}.desktop" "${appdir_stage}/${APP_ID}.desktop"
    install -Dm0644 "${SCRIPT_DIR}/assets/${APP_ID}.svg" "${appdir_stage}/${APP_ID}.svg"
    install -Dm0644 "${SCRIPT_DIR}/${APP_ID}.desktop" \
        "${appdir_stage}/usr/share/applications/${APP_ID}.desktop"
    install -Dm0644 "${SCRIPT_DIR}/assets/${APP_ID}.svg" \
        "${appdir_stage}/usr/share/icons/hicolor/scalable/apps/${APP_ID}.svg"
    mkdir -p -- "${appdir_stage}/usr/bin"
    ln -s "../lib/${APP_ID}/WireWizardGUI" "${appdir_stage}/usr/bin/${APP_ID}"
    find "${appdir_stage}" -exec touch -h -d "@${SOURCE_DATE_EPOCH}" {} +
    publish_output_directory "${appdir_stage}" "${APPDIR_OUTPUT}"

    [[ -x "${APPDIR_OUTPUT}/AppRun" ]] || die "AppDir validation failed: AppRun is not executable"
    [[ -f "${APPDIR_OUTPUT}/${APP_ID}.desktop" ]] || die "AppDir validation failed: desktop file is missing"
fi

if [[ -n "${REQUESTED[appimage]:-}" ]]; then
    appimage_output="${OUTPUT_DIR}/${APP_NAME}-${VERSION}-${APPIMAGE_ARCH}.AppImage"
    appimagetool_path=""
    appimagetool_runtime_args=()
    if [[ "${APPIMAGETOOL}" == */* ]]; then
        [[ -x "${APPIMAGETOOL}" ]] && appimagetool_path="${APPIMAGETOOL}"
    else
        appimagetool_path="$(command -v "${APPIMAGETOOL}" 2>/dev/null || true)"
    fi

    if [[ -n "${appimagetool_path}" ]]; then
        if [[ -n "${APPIMAGE_RUNTIME_FILE}" ]]; then
            [[ -f "${APPIMAGE_RUNTIME_FILE}" && -r "${APPIMAGE_RUNTIME_FILE}" ]] || \
                die "APPIMAGE_RUNTIME_FILE is not a readable file: ${APPIMAGE_RUNTIME_FILE}"
            appimage_runtime_path="$(readlink -f -- "${APPIMAGE_RUNTIME_FILE}")"
            appimagetool_runtime_args+=(--runtime-file "${appimage_runtime_path}")
        fi
        log "Converting AppDir to AppImage"
        prepare_output_file "${appimage_output}"
        appimage_staged="${WORK_DIR}/${APP_NAME}-${VERSION}-${APPIMAGE_ARCH}.AppImage"
        ARCH="${APPIMAGE_ARCH}" "${appimagetool_path}" "${appimagetool_runtime_args[@]}" "${APPDIR_OUTPUT}" "${appimage_staged}"
        chmod 0755 "${appimage_staged}"
        mv -- "${appimage_staged}" "${appimage_output}"
    else
        warn "appimagetool not found; AppDir is ready at ${APPDIR_OUTPUT}"
        warn "Set APPIMAGETOOL=/path/to/appimagetool OVERWRITE=1 and rerun to create .AppImage"
    fi
fi

if [[ -n "${REQUESTED[deb]:-}" ]]; then
    deb_root="${WORK_DIR}/deb-root"
    deb_payload="${deb_root}/opt/${APP_ID}"
    deb_output="${OUTPUT_DIR}/${APP_ID}_${VERSION}_${DEB_ARCH}.deb"

    log "Creating Debian package"
    make_payload "${deb_payload}" installed
    strip_bundled_graphviz "${deb_payload}"
    install -Dm0644 "${SCRIPT_DIR}/${APP_ID}.desktop" \
        "${deb_root}/usr/share/applications/${APP_ID}.desktop"
    install -Dm0644 "${SCRIPT_DIR}/assets/${APP_ID}.svg" \
        "${deb_root}/usr/share/icons/hicolor/scalable/apps/${APP_ID}.svg"
    install -Dm0644 "${PROJECT_ROOT}/LICENSE" \
        "${deb_root}/usr/share/doc/${APP_ID}/copyright"
    install -Dm0644 "${PROJECT_ROOT}/THIRD_PARTY_NOTICES.md" \
        "${deb_root}/usr/share/doc/${APP_ID}/THIRD_PARTY_NOTICES.md"
    mkdir -p -- "${deb_root}/usr/bin" "${deb_root}/DEBIAN"
    ln -s "../../opt/${APP_ID}/WireWizardGUI" "${deb_root}/usr/bin/${APP_ID}"

    installed_size="$(du -sk "${deb_root}" | awk '{print $1}')"
    sed \
        -e "s/@VERSION@/${VERSION}/g" \
        -e "s/@ARCH@/${DEB_ARCH}/g" \
        -e "s/@INSTALLED_SIZE@/${installed_size}/g" \
        "${SCRIPT_DIR}/control.in" >"${deb_root}/DEBIAN/control"
    chmod 0644 "${deb_root}/DEBIAN/control"
    find "${deb_root}" -exec touch -h -d "@${SOURCE_DATE_EPOCH}" {} +

    if command -v desktop-file-validate >/dev/null 2>&1; then
        desktop-file-validate "${deb_root}/usr/share/applications/${APP_ID}.desktop"
    fi

    prepare_output_file "${deb_output}"
    deb_staged="${WORK_DIR}/${APP_ID}_${VERSION}_${DEB_ARCH}.deb"
    dpkg-deb --root-owner-group --build "${deb_root}" "${deb_staged}"
    mv -- "${deb_staged}" "${deb_output}"
    dpkg-deb --info "${deb_output}" >/dev/null
fi

log "Build completed. Artifacts: ${OUTPUT_DIR}"
