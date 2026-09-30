#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Run actionlint from a verified, versioned release archive, leaving any system
# installation alone. Arguments are passed directly to actionlint.
set -eu

actionlint_version=1.7.12
case "$(uname -s):$(uname -m)" in
    Linux:aarch64|Linux:arm64)
        actionlint_arch=arm64
        actionlint_sha=325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6
        ;;
    Linux:x86_64|Linux:amd64)
        actionlint_arch=amd64
        actionlint_sha=8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8
        ;;
    *)
        echo 'The pinned actionlint supports Linux amd64 and arm64.' >&2
        exit 1
        ;;
esac

# Checksums are from the release's actionlint_1.7.12_checksums.txt.
actionlint_name="actionlint_${actionlint_version}_linux_${actionlint_arch}"
actionlint_root=${ACTIONLINT_ROOT:-"${HOME}/build/toolchains"}
mkdir -p -- "$actionlint_root"
actionlint_root=$(cd "$actionlint_root" && pwd -P)
actionlint_prefix="$actionlint_root/$actionlint_name"

# The per-edition lock covers download and publication. A second invocation sees
# either a complete installation or waits; interruption leaves no partial prefix.
(
    flock -x 9
    if [ ! -x "$actionlint_prefix/actionlint" ]; then
        if [ -e "$actionlint_prefix" ]; then
            echo "Incomplete actionlint installation at $actionlint_prefix; inspect it before retrying." >&2
            exit 1
        fi
        actionlint_stage=$(mktemp -d "$actionlint_root/.${actionlint_name}.XXXXXX")
        trap 'rm -rf -- "$actionlint_stage"' 0
        trap 'exit 1' HUP INT TERM
        echo "Installing actionlint $actionlint_version ($actionlint_arch) in $actionlint_prefix" >&2
        curl --fail --silent --show-error --location --retry 3 \
            --output "$actionlint_stage/archive.tar.gz" \
            "https://github.com/rhysd/actionlint/releases/download/v${actionlint_version}/${actionlint_name}.tar.gz"
        printf '%s  %s\n' "$actionlint_sha" "$actionlint_stage/archive.tar.gz" | sha256sum --check --status
        mkdir -- "$actionlint_stage/$actionlint_name"
        tar -xzf "$actionlint_stage/archive.tar.gz" -C "$actionlint_stage/$actionlint_name"
        [ "$("$actionlint_stage/$actionlint_name/actionlint" -version | head -n 1)" = "$actionlint_version" ]
        mv -- "$actionlint_stage/$actionlint_name" "$actionlint_prefix"
    fi
    if [ "$("$actionlint_prefix/actionlint" -version | head -n 1)" != "$actionlint_version" ]; then
        echo "Unexpected actionlint version at $actionlint_prefix; inspect it before retrying." >&2
        exit 1
    fi
) 9>"$actionlint_root/.${actionlint_name}.lock"

exec "$actionlint_prefix/actionlint" "$@"
