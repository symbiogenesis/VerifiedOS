#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Run the Wasm oracle with a verified, versioned Node installation, leaving the
# system runtime alone. Arguments are passed directly to Node.
set -eu

node_version=26.8.2
case "$(uname -s):$(uname -m)" in
    Linux:aarch64|Linux:arm64)
        node_arch=arm64
        node_sha=81d8f0fdea9dcd3bfdcfeafc5f8359c151f097e9880b0007c0645ca670d07971
        ;;
    Linux:x86_64|Linux:amd64)
        node_arch=x64
        node_sha=40e1d3225c1c9ae9a2671c98ecb9857e4d5555026394f348645676798840d5c5
        ;;
    *)
        echo 'The oracle Node runtime supports Linux x64 and arm64.' >&2
        exit 1
        ;;
esac

# Checksums are from https://nodejs.org/dist/v26.8.2/SHASUMS256.txt.
node_name="node-v${node_version}-linux-${node_arch}"
node_root=${NODE_TOOLCHAIN_ROOT:-"${HOME}/build/toolchains"}
mkdir -p -- "$node_root"
node_root=$(cd "$node_root" && pwd -P)
node_prefix="$node_root/$node_name"

# The per-edition lock covers download and publication. A second invocation sees
# either a complete installation or waits; interruption leaves no partial prefix.
(
    flock -x 9
    if [ ! -x "$node_prefix/bin/node" ]; then
        if [ -e "$node_prefix" ]; then
            echo "Incomplete Node installation at $node_prefix; inspect it before retrying." >&2
            exit 1
        fi
        node_stage=$(mktemp -d "$node_root/.${node_name}.XXXXXX")
        trap 'rm -rf -- "$node_stage"' 0
        trap 'exit 1' HUP INT TERM
        echo "Installing Node.js v$node_version ($node_arch) in $node_prefix" >&2
        curl --fail --silent --show-error --location --retry 3 \
            --output "$node_stage/archive.tar.xz" \
            "https://nodejs.org/dist/v${node_version}/${node_name}.tar.xz"
        printf '%s  %s\n' "$node_sha" "$node_stage/archive.tar.xz" | sha256sum --check --status
        tar -xJf "$node_stage/archive.tar.xz" -C "$node_stage"
        [ "$("$node_stage/$node_name/bin/node" --version)" = "v$node_version" ]
        mv -- "$node_stage/$node_name" "$node_prefix"
    fi
    if [ "$("$node_prefix/bin/node" --version)" != "v$node_version" ]; then
        echo "Unexpected Node version at $node_prefix; inspect it before retrying." >&2
        exit 1
    fi
) 9>"$node_root/.${node_name}.lock"

exec "$node_prefix/bin/node" "$@"
