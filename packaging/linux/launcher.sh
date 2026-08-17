#!/bin/sh

set -eu

resolved_self="$(readlink -f -- "$0")"
app_home="$(CDPATH= cd -- "$(dirname -- "${resolved_self}")" && pwd -P)"

if [ -f "${app_home}/portable.flag" ]; then
    WIREWIZARD_PORTABLE=1
    export WIREWIZARD_PORTABLE
    if [ -z "${WIREWIZARD_DATA_DIR:-}" ]; then
        WIREWIZARD_DATA_DIR="${app_home}/data"
        export WIREWIZARD_DATA_DIR
    fi
fi

# The common PyInstaller spec places bundled data below _internal. Keep the
# other two candidates so a manually supplied onedir layout also works.
graphviz_root="${WIREWIZARD_GRAPHVIZ_DIR:-}"
if [ -z "${graphviz_root}" ]; then
    for candidate in \
        "${app_home}/app/_internal/graphviz" \
        "${app_home}/app/graphviz" \
        "${app_home}/graphviz"; do
        if [ -x "${candidate}/bin/dot" ]; then
            graphviz_root="${candidate}"
            break
        fi
    done
fi

if [ -n "${graphviz_root}" ] && [ -x "${graphviz_root}/bin/dot" ]; then
    PATH="${graphviz_root}/bin:${PATH}"
    export PATH

    for library_dir in \
        "${graphviz_root}/lib" "${graphviz_root}"/lib/* \
        "${graphviz_root}/lib64" "${graphviz_root}"/lib64/*; do
        if [ -d "${library_dir}" ]; then
            LD_LIBRARY_PATH="${library_dir}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
        fi
    done
    export LD_LIBRARY_PATH

    for plugin_dir in \
        "${graphviz_root}/lib/graphviz" "${graphviz_root}"/lib/*/graphviz \
        "${graphviz_root}/lib64/graphviz" "${graphviz_root}"/lib64/*/graphviz; do
        if [ -d "${plugin_dir}" ]; then
            GVBINDIR="${plugin_dir}"
            export GVBINDIR
            break
        fi
    done
fi

exec "${app_home}/app/WireWizardGUI" "$@"
