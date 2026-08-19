# CMake options for test downloads
set(TEST_DOWNLOAD_URL "https://github.com/riscv-software-src/sail-riscv-tests/releases/download" CACHE STRING "Base URL to download precompiled riscv-tests and riscv-vector-tests from")
set(TEST_DOWNLOAD_VERSION "2026-06-10" CACHE STRING "Version of precompiled tests to download")

# Function to download and extract test files
function(download_riscv_tests DOWNLOAD_PATH TARBALL_NAME DOWNLOAD_URL)
    if(NOT EXISTS "${DOWNLOAD_PATH}/${TARBALL_NAME}")
        if(NOT EXISTS "${DOWNLOAD_PATH}/${TARBALL_NAME}.tar.gz")
            message(STATUS "${TARBALL_NAME}.tar.gz not found, downloading...")

            # Download the tar.gz file
            file(DOWNLOAD
                "${DOWNLOAD_URL}"
                "${DOWNLOAD_PATH}/${TARBALL_NAME}.tar.gz"
                SHOW_PROGRESS
                STATUS download_status
            )

            # Check download status
            list(GET download_status 0 status_code)
            if(NOT status_code EQUAL 0)
                list(GET download_status 1 error_message)
                message(FATAL_ERROR "Failed to download ${TARBALL_NAME}: ${error_message}")
            endif()
        endif()

        # Create directory and extract the tar.gz file into it
        file(MAKE_DIRECTORY "${DOWNLOAD_PATH}/${TARBALL_NAME}")
        execute_process(
            COMMAND ${CMAKE_COMMAND} -E tar xzf "${DOWNLOAD_PATH}/${TARBALL_NAME}.tar.gz"
            WORKING_DIRECTORY "${DOWNLOAD_PATH}/${TARBALL_NAME}"
            RESULT_VARIABLE extract_result
        )

        if(NOT extract_result EQUAL 0)
            message(FATAL_ERROR "Failed to extract ${TARBALL_NAME}")
        endif()

        # Clean up the tar.gz file
        file(REMOVE "${DOWNLOAD_PATH}/${TARBALL_NAME}.tar.gz")
        message(STATUS "${TARBALL_NAME} downloaded and extracted successfully")
    endif()
endfunction()

function(setup_vector_test vlen elen)
    option(ENABLE_RISCV_VECTOR_TESTS_V${vlen}_E${elen}
        "Enable riscv-vector-tests with vlen=${vlen}, elen=${elen}"
        OFF)

    if(ENABLE_RISCV_VECTOR_TESTS_V${vlen}_E${elen})
        set(TARBALL_NAME "riscv-vector-tests-v${vlen}x${elen}")
        set(DOWNLOAD_PATH "${CMAKE_CURRENT_BINARY_DIR}/${TEST_DOWNLOAD_VERSION}")
        set(DOWNLOAD_URL "${TEST_DOWNLOAD_URL}/${TEST_DOWNLOAD_VERSION}/${TARBALL_NAME}.tar.gz")

        download_riscv_tests(
            "${DOWNLOAD_PATH}"
            "${TARBALL_NAME}"
            "${DOWNLOAD_URL}"
        )

        # These tests use XLEN=ELEN. There are no tests with XLEN=64 & ELEN=32 or vice versa.
        set(xlen ${elen})

        file(GLOB elfs CONFIGURE_DEPENDS LIST_DIRECTORIES false
            "${DOWNLOAD_PATH}/${TARBALL_NAME}/rv${xlen}*"
        )

        foreach(elf IN LISTS elfs)
            file(RELATIVE_PATH elf_name "${CMAKE_CURRENT_BINARY_DIR}" ${elf})
            add_test(
                # `elf_name` includes xlen/vlen/elen so we don't need to add any details.
                NAME "${elf_name}"
                COMMAND
                    $<TARGET_FILE:sail_riscv_sim>
                    --config "${CMAKE_BINARY_DIR}/config/rv${xlen}d_v${vlen}_e${elen}.json"
                    ${elf}
            )
        endforeach()
    endif()
endfunction()

# Download and add RVV tests.
# NOTE: Setting XLEN independently of ELEN is not
# supported by the RISC-V Vector Test suite.
foreach(vlen IN ITEMS 64 128 256 512)
    foreach(elen IN ITEMS 32 64)
        if((${vlen} EQUAL 512) AND (${elen} EQUAL 32))
            # The test suite for this combination is not built due to
            # its long execution time.
            continue()
        endif()
        setup_vector_test("${vlen}" "${elen}")
    endforeach()
endforeach()

# Download and add RISC-V tests.
option(ENABLE_RISCV_TESTS "Enable riscv-tests" OFF)

function(filter_riscv_tests test_elfs elfs_to_use_varname)
    # These tests exercise surface the frozen profile deletes
    # (docs/isa-profile.md, M0.6c). They are excluded rather than expected
    # to fail: the instructions they execute no longer decode.

    # Zalrsc: no load-reserved/store-conditional (R-15-024).
    list(FILTER test_elfs EXCLUDE REGEX ".*/rv(32|64)ua-[pv]-lrsc$")

    # Zifencei: no instruction-fetch fence.  This takes three groups with it,
    # not just the instruction's own test:
    #   - the `fence_i` tests themselves,
    #   - `uziccid`, which executes FENCE.I directly to test fetch coherence,
    #   - the whole `-v-` (virtual-memory) half, whose shared riscv-tests
    #     environment runs FENCE.I in its page-fault handler, so every `-v-`
    #     binary traps into an unhandled illegal instruction regardless of
    #     what it was written to test.
    # The `-v-` half was booked for removal with the S/U and translation cut;
    # FENCE.I's absence brings it forward to this batch.
    list(FILTER test_elfs EXCLUDE REGEX ".*/rv(32|64)ui-[pv]-fence_i$")
    list(FILTER test_elfs EXCLUDE REGEX ".*/rv(32|64)uziccid-[pv]-ziccid$")
    list(FILTER test_elfs EXCLUDE REGEX ".*-v-.*")

    # C: no compressed instructions (R-15-007a); ILEN is fixed at 32 bits, so
    # every 16-bit parcel is an illegal instruction.
    list(FILTER test_elfs EXCLUDE REGEX ".*/rv(32|64)uc-[pv]-rvc$")

    # Zicntr: no unprivileged or machine cycle/time/instret CSRs (R-15-077).
    # `instret_overflow` goes with it: it writes `minstret` to set up the
    # overflow it tests, and that CSR no longer exists.
    list(FILTER test_elfs EXCLUDE REGEX ".*/rv(32|64)mi-[pv]-zicntr$")
    list(FILTER test_elfs EXCLUDE REGEX ".*/rv(32|64)mi-[pv]-instret_overflow$")

    set(${elfs_to_use_varname} "${test_elfs}" PARENT_SCOPE)
endfunction()

if(ENABLE_RISCV_TESTS)
    set(TARBALL_NAME "riscv-tests")
    set(DOWNLOAD_PATH "${CMAKE_CURRENT_BINARY_DIR}/${TEST_DOWNLOAD_VERSION}")
    set(DOWNLOAD_URL "${TEST_DOWNLOAD_URL}/${TEST_DOWNLOAD_VERSION}/${TARBALL_NAME}.tar.gz")

    download_riscv_tests(
        "${DOWNLOAD_PATH}"
        "${TARBALL_NAME}"
        "${DOWNLOAD_URL}"
    )

    foreach(xlen IN ITEMS 32 64)
        file(GLOB elf_list CONFIGURE_DEPENDS LIST_DIRECTORIES false
           "${DOWNLOAD_PATH}/${TARBALL_NAME}/rv${xlen}*"
        )

        # Drop the tests for deleted profile surface.
        filter_riscv_tests("${elf_list}" elf_list)

        foreach(elf IN LISTS elf_list)
            file(RELATIVE_PATH elf_name "${CMAKE_CURRENT_BINARY_DIR}" ${elf})
            add_test(
                # `elf_name` includes xlen so we don't need to add any details.
                NAME "${elf_name}"
                COMMAND
                    $<TARGET_FILE:sail_riscv_sim>
                    # Use ELEN=XLEN. These tests don't use vector so it doesn't actually matter.
                    --config "${CMAKE_BINARY_DIR}/config/rv${xlen}d_v256_e${xlen}.json"
                    ${elf}
            )
        endforeach()
    endforeach()
endif()

# Download and add RISC-V arch tests.
option(ENABLE_RISCV_ARCH_TESTS "Enable riscv-arch-tests" OFF)

function(filter_arch_tests test_elfs elfs_to_use_varname)
    # These tests pass with a config matching the one used in
    # `riscv-arch-test`, but which differs from the ones generated in
    # our build.  They can be re-enabled once we support more granular
    # test-specific configurations in CI.
    list(FILTER test_elfs EXCLUDE REGEX ".*/InterruptsS-00\\.elf$")
    list(FILTER test_elfs EXCLUDE REGEX ".*/InterruptsSm-00\\.elf$")
    list(FILTER test_elfs EXCLUDE REGEX ".*/S-00\\.elf$")
    list(FILTER test_elfs EXCLUDE REGEX ".*/SsstrictS-01\\.elf$")
    list(FILTER test_elfs EXCLUDE REGEX ".*/UV-00\\.elf$")

    # These tests fail because
    # https://github.com/riscv/sail-riscv/pull/1690 strengthened illegal
    # instruction checks for vector instructions (like vbrev8).
    # Instructions that executed with the 0.11 release now raise illegal
    # instruction exceptions with the current version.
    list(FILTER test_elfs EXCLUDE REGEX ".*/SsstrictSm-14\\.elf$")

    # These tests similarly fail because
    # https://github.com/riscv/sail-riscv/pull/1698 strengthens checks
    # for vector source register overlaps (like vwadd.vv).
    list(FILTER test_elfs EXCLUDE REGEX ".*/SsstrictSm-13\\.elf$")

    # These RV64 tests fail because
    # https://github.com/riscv/sail-riscv/pull/1712 fixed an incorrect
    # decoding of add.uw, and now correctly treats that encoding as
    # reserved and traps with an illegal instruction exception.
    list(FILTER test_elfs EXCLUDE REGEX ".*/sail-rv64-max/.*/SsstrictS-06\\.elf$")
    list(FILTER test_elfs EXCLUDE REGEX ".*/sail-rv64-max/.*/SsstrictSm-06\\.elf$")
    list(FILTER test_elfs EXCLUDE REGEX ".*/sail-rv64-max/.*/SsstrictU-02\\.elf$")

    # These tests fail because
    # https://github.com/riscv/sail-riscv/pull/1734 does not raise
    # exceptions for misaligned atomics before address translation by
    # default.  Instead, exception behavior in these cases is handled
    # by the MAG PMA.  These tests pass if `misaligned.exceptions.amo`
    # is specified with the previous default value (`"Some": "AccessFault"`).
    list(FILTER test_elfs EXCLUDE REGEX ".*/sv3[29]_exceptions_Zaamo_[MSU]mode\\.elf$")
    list(FILTER test_elfs EXCLUDE REGEX ".*/ExceptionsZaamo-00\\.elf$")
    list(FILTER test_elfs EXCLUDE REGEX ".*/Zama16b-00\\.elf$")

    set(${elfs_to_use_varname} "${test_elfs}" PARENT_SCOPE)
endfunction()

if(ENABLE_RISCV_ARCH_TESTS)
    set(TARBALL_NAME "riscv-arch-tests")
    set(DOWNLOAD_PATH "${CMAKE_CURRENT_BINARY_DIR}/${TEST_DOWNLOAD_VERSION}")
    set(DOWNLOAD_URL "${TEST_DOWNLOAD_URL}/${TEST_DOWNLOAD_VERSION}/${TARBALL_NAME}.tar.gz")

    download_riscv_tests(
        "${DOWNLOAD_PATH}"
        "${TARBALL_NAME}"
        "${DOWNLOAD_URL}"
    )

    foreach(xlen IN ITEMS 32 64)
        file(GLOB_RECURSE elf_list CONFIGURE_DEPENDS LIST_DIRECTORIES false
           "${DOWNLOAD_PATH}/${TARBALL_NAME}/sail-rv${xlen}-max/*.elf"
        )

        # Filter out tests that fail for a good reason.
        filter_arch_tests("${elf_list}" elfs_to_use)

        foreach(elf IN LISTS elfs_to_use)
            file(RELATIVE_PATH elf_name "${CMAKE_CURRENT_BINARY_DIR}" ${elf})
            add_test(
                # `elf_name` includes xlen so we don't need to add any details.
                NAME "${elf_name}"
                COMMAND
                    $<TARGET_FILE:sail_riscv_sim>
                    # Use ELEN=XLEN. These tests don't yet use vector so it doesn't matter.
                    --config "${CMAKE_BINARY_DIR}/config/rv${xlen}d_v256_e${xlen}.json"
                    ${elf}
            )
        endforeach()
    endforeach()
endif()

# Download and add Lean emulator tests.
option(ENABLE_LEAN_EMULATOR_TESTS "Enable Lean emulator tests" OFF)

if(ENABLE_LEAN_EMULATOR_TESTS)
    set(TARBALL_NAME "riscv-tests")
    set(DOWNLOAD_PATH "${CMAKE_CURRENT_BINARY_DIR}/${TEST_DOWNLOAD_VERSION}")
    set(DOWNLOAD_URL "${TEST_DOWNLOAD_URL}/${TEST_DOWNLOAD_VERSION}/${TARBALL_NAME}.tar.gz")

    download_riscv_tests(
        "${DOWNLOAD_PATH}"
        "${TARBALL_NAME}"
        "${DOWNLOAD_URL}"
    )

    include(lean_emulator_test_files.cmake)
    set(lean_emulator ${CMAKE_BINARY_DIR}/lean-emulator-build/build/bin/lean_riscv_emulator)
    foreach(elf IN LISTS lean_elf_files)
        add_test(
            NAME "lean_emulator_${elf}"
            COMMAND
              ${lean_emulator}
              ${DOWNLOAD_PATH}/riscv-tests/${elf}
        )
    endforeach()
endif()

# This is off by default so we don't require people who
# just want to build the model to have Clang or RISC-V GCC
# installed.
option(FIRST_PARTY_TESTS "Compile & run first party tests (requires Clang or RISC-V GCC).")
if (FIRST_PARTY_TESTS)
    add_subdirectory("first_party")
endif()

add_subdirectory("unit_tests")
