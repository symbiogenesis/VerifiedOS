# SPDX-License-Identifier: Apache-2.0
# The host-side CertiCoq -> Wasm oracle (implementation-checklist §0, M1.5):
# Gallina components exercised on a stock Wasm engine, no cross-toolchain, no
# image, no machine model. This container is that engine's pinned environment.
#
# Rocq 9.1.1 is deliberate, not stale: CertiRocq constrains
# rocq >= 9.1 & < 9.2~, and SECOMP (upstream/SECOMP, M1.2) states Rocq 9.1 too,
# so one prover version serves both legs.
#
# The image is published for linux/amd64 only, at every 9.1 tag, so on an arm64
# host this path wants emulation and the native recipe in README.md is the one
# that runs.
FROM rocq/rocq-prover:9.1-ocaml-4.14-flambda

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends clang nodejs npm \
    && rm -rf /var/lib/apt/lists/*
# On a TLS-intercepting network (Cisco Umbrella here), place the proxy root CA
# beside this Dockerfile as proxy-root-ca.crt and uncomment:
# COPY proxy-root-ca.crt /usr/local/share/ca-certificates/
# RUN update-ca-certificates

USER rocq
# CertiRocq 0.9.1 for Rocq 9.1 is a released package that carries the merged
# CertiCoq-Wasm backend (theories/CodegenWasm, mechanized against WasmCert-Coq;
# CPP 2025) and takes released MetaRocq 1.5.1, which is both halves of what a
# source pin and a compat patch used to buy here. The release is the whole
# environment: no clone, no checkout, no patch.
ARG CERTIROCQ_VERSION=0.9.1+9.1
RUN opam repo list --all | grep -q rocq-released \
    || opam repo add rocq-released https://rocq-prover.org/opam/released
RUN opam install -y rocq-certirocq.${CERTIROCQ_VERSION}

WORKDIR /home/rocq/oracle
COPY --chown=rocq:rocq demo.v run_demo.mjs ./
