# SPDX-License-Identifier: Apache-2.0
# The host-side CertiCoq -> Wasm oracle (implementation-checklist §0, M1.5):
# Gallina components exercised on a stock Wasm engine, no cross-toolchain, no
# image, no machine model. This container is that engine's pinned environment.
#
# CertiRocq and coq-wasm constrain this oracle to Rocq 9.1. The proof gate
# independently uses Rocq 9.2. The image supplies a bootstrap environment;
# the project switch below supplies the updated compiler and libraries.
#
# The image is published for linux/amd64 only, at every 9.1 tag, so on an arm64
# host this path wants emulation and the native recipe in README.md is the one
# that runs.
FROM rocq/rocq-prover:9.1-ocaml-4.14-flambda

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends clang curl xz-utils util-linux ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# On a TLS-intercepting network (Cisco Umbrella here), place the proxy root CA
# beside this Dockerfile as proxy-root-ca.crt and uncomment:
# COPY wasm-oracle/proxy-root-ca.crt /usr/local/share/ca-certificates/
# RUN update-ca-certificates

USER rocq
# CertiRocq 0.9.1 for Rocq 9.1 is a released package that carries the merged
# CertiCoq-Wasm backend (theories/CodegenWasm, mechanized against WasmCert-Coq;
# CPP 2025) and takes released MetaRocq 1.5.1, which is both halves of what a
# source pin and a compat patch used to buy here. The release is the whole
# environment: no clone, no checkout, no patch.
ARG OCAML_VERSION=5.4.1
ARG TOOLCHAIN_SWITCH=verifiedos-certirocq-0.9.1-ocaml-${OCAML_VERSION}
COPY --chown=rocq:rocq opam/certirocq.lock /tmp/certirocq.lock
RUN opam repo list --all | grep -q rocq-released \
    || opam repo add rocq-released https://rocq-prover.org/opam/released
RUN opam update --all \
    && opam switch create "${TOOLCHAIN_SWITCH}" --empty \
       --repos=rocq-released,default --no-switch -y \
    && opam switch import --switch="${TOOLCHAIN_SWITCH}" /tmp/certirocq.lock -y
ENV OPAMSWITCH=${TOOLCHAIN_SWITCH}
ENV PATH=/home/rocq/.opam/${OPAMSWITCH}/bin:${PATH}

WORKDIR /home/rocq/oracle
COPY --chown=rocq:rocq wasm-oracle/demo.v wasm-oracle/run_demo.mjs wasm-oracle/node.sh ./
RUN sh node.sh --version
