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
# supported by the RISC-V Vector Test suite, so ELEN=32 would mean an RV32
# hart, which is not a configuration of this model (model/core/xlen.sail).
foreach(vlen IN ITEMS 64 128 256 512)
    setup_vector_test("${vlen}" 64)
endforeach()

# Download and add RISC-V tests.
option(ENABLE_RISCV_TESTS "Enable riscv-tests" OFF)

function(filter_riscv_tests test_elfs elfs_to_use_varname)
    # `riscv-tests` is not a corpus this machine can run, and the ground is one
    # sentence rather than a list of extensions: every program in it addresses
    # memory with an *integer* base register, and on a purecap machine a base
    # register holds a capability, so an integer written into one is an untagged
    # capability that faults at the first load or store the program performs
    # (R-15-001, R-15-001c, R-15-007h).  There is no default data capability to
    # authorise the access instead, and there is no mode in which the base
    # register is read as an integer.
    #
    # So the whole suite is excluded from registration rather than filtered
    # family by family.  The ELFs are still downloaded and still useful: the
    # profile sweep (`tools/model.py sweep`) runs them against the profile
    # configuration and classifies what it refuses, which is a different
    # question from whether the model is a correct implementation of what it
    # implements.
    #
    # What answers *that* question now is the model's own `$[test]` harness
    # (`model/unit_tests/`), until the purecap programs of M0.12 exist.
    list(FILTER test_elfs EXCLUDE REGEX ".*")

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

    # RV64 only: RV32 is not a configuration of this model
    # (model/core/xlen.sail), so the `rv32*` half of the corpus has no
    # machine to run on and is not registered.
    file(GLOB elf_list CONFIGURE_DEPENDS LIST_DIRECTORIES false
       "${DOWNLOAD_PATH}/${TARBALL_NAME}/rv64*"
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
                # These tests don't use vector so ELEN doesn't actually matter.
                --config "${CMAKE_BINARY_DIR}/config/rv64d_v256_e64.json"
                ${elf}
        )
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

    # RV64 only, as above.
    file(GLOB_RECURSE elf_list CONFIGURE_DEPENDS LIST_DIRECTORIES false
       "${DOWNLOAD_PATH}/${TARBALL_NAME}/sail-rv64-max/*.elf"
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
                # These tests don't yet use vector so ELEN doesn't matter.
                --config "${CMAKE_BINARY_DIR}/config/rv64d_v256_e64.json"
                ${elf}
        )
    endforeach()
endif()

# There is no `first_party` directory and no `FIRST_PARTY_TESTS` option, and the
# ground is the one that retired `riscv-tests` above rather than a second one.
# Every program in that set was an ordinary RV64 program: `crt0.S` opened by
# writing integer zero over all thirty-one registers, `c1` among them, and then
# addressed its own stack, global pointer and HTIF exit door through integer base
# registers.  On a purecap machine an integer written into a register is an
# untagged capability, so that prologue destroys the store-side root it was handed
# at reset and then faults at its first store, before `main` (R-15-001, R-15-001c,
# R-15-007h, R-15-007p; model/core/addr_checks.sail).  No `-march` string and no
# curated subset reaches past that: what the set needs is the purecap toolchain,
# whose `la` derives a capability off PCC rather than materializing an integer,
# and that is M1.4's.
#
# What answers the question the set was asked is this repository's own pair, the
# model's `$[test]` harness (model/unit_tests/) and the differential corpus
# (corpus/), both of which are purecap programs against this machine rather than
# stock RISC-V programs against a machine it no longer is.

add_subdirectory("unit_tests")
