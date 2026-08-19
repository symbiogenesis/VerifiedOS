# The host-side CertiCoq -> Wasm oracle (implementation-checklist §0, M1.5):
# Gallina components exercised on a stock Wasm engine, no cross-toolchain, no
# image, no machine model. This container is that engine's pinned environment.
#
# Rocq 9.1.1 is deliberate, not stale: CertiRocq main constrains
# rocq >= 9.1 & < 9.2~, and SECOMP (upstream/SECOMP, M1.2) states Rocq 9.1 too,
# so one prover version serves both legs.
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
# CertiRocq main carries the merged CertiCoq-Wasm backend (CodegenWasm,
# mechanized against WasmCert-Coq; CPP 2025); the 0.9 opam release predates
# it, hence the source pin. Main's tip tracks the unreleased MetaRocq 9.1
# branch, so the pin is the last commit before that drift (4f53ca97, June 9
# 2026) plus a two-site compat patch for where released MetaRocq 1.5.1 moved
# the erasure inlining toggle into unsafe_passes.
ARG CERTIROCQ_SHA=4f53ca97303847cfb41265ac676e324703f77dcd
COPY --chown=rocq:rocq metarocq-1.5.1-compat.patch /tmp/
RUN git clone https://github.com/CertiCoq/certicoq.git /home/rocq/certicoq \
    && cd /home/rocq/certicoq \
    && git checkout ${CERTIROCQ_SHA} \
    && git apply /tmp/metarocq-1.5.1-compat.patch \
    && git -c user.email=oracle@local -c user.name=oracle commit -aqm "metarocq 1.5.1 compat" \
    && opam pin -n -y . \
    && opam install -y rocq-certirocq

WORKDIR /home/rocq/oracle
COPY --chown=rocq:rocq demo.v run_demo.mjs ./
