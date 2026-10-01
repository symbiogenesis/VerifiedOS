# CMake options for test downloads
set(TEST_DOWNLOAD_URL "https://github.com/riscv-software-src/sail-riscv-tests/releases/download" CACHE STRING "Base URL to download precompiled riscv-tests and riscv-vector-tests from")
set(TEST_DOWNLOAD_VERSION "2026-08-20" CACHE STRING "Version of precompiled tests to download")

# The SHA-256 of every release asset this file can download, as the GitHub
# release publishes it, keyed by release and tarball name. Configure refuses an
# enabled suite whose tarball has no digest here at the selected release, so
# selecting another release means recording its digests first.
set(TEST_DOWNLOAD_SHA256_2026-08-20_riscv-tests "eb24265e83ca0b68a24a513dff7e4535975e724fe07d71f3cf75fef87fd75bec")
set(TEST_DOWNLOAD_SHA256_2026-08-20_riscv-arch-tests "c07ba4f475e96395d77287e1fd471a4a43af47d09f121393f61812158462b3c1")
set(TEST_DOWNLOAD_SHA256_2026-08-20_riscv-vector-tests-v64x64 "07bc6b49f4078a76c278f3ab91fed25c7012693164dd1b0af26e9cb4a759e5cb")
set(TEST_DOWNLOAD_SHA256_2026-08-20_riscv-vector-tests-v128x64 "a9c91631d4bb3c9f6af0463fcd81eb00a1f849170bb50f6dcfe844c92c8e8e76")
set(TEST_DOWNLOAD_SHA256_2026-08-20_riscv-vector-tests-v256x64 "a4d150a38e5226bdd40bee9c15ba6d29d5474f25cc7206e1d57c15ae965e785f")
set(TEST_DOWNLOAD_SHA256_2026-08-20_riscv-vector-tests-v512x64 "a968025ffd35fa9cb301ed9fb84c4108473ea9ec696f19e17b42a54857c92acf")

# The listing an extracted suite is held to, which download_riscv_tests records
# as <suite>.manifest beside a suite it has just extracted from a verified
# tarball: the tarball's recorded SHA-256, then the SHA-256 and relative path of
# every file in the suite, sorted by path. A symbolic link is listed unhashed,
# and every name holding ";" or "\" leaves at least one unhashed line (see the
# check before the sort and the loop below). No manifest is written holding an
# unhashed line. Configure does not tell a FIFO or device node from a file, and
# reading one can stall it. The verified riscv-tests tarball contains neither,
# and the listing tools/vos/cli/model.py renders for the readers that do not
# configure refuses both.
function(riscv_tests_listing SUITE TARBALL_NAME EXPECTED_SHA256 OUT_VAR)
    set(listing "tarball ${TARBALL_NAME}.tar.gz sha256 ${EXPECTED_SHA256}\n")
    file(GLOB_RECURSE paths LIST_DIRECTORIES false "${SUITE}/*")
    # CMake's list splitting takes a "\" before a ";" as escaping that ";".
    # A name ending in "\", whose path the glob joins to the next with ";",
    # or holding "\;" therefore reaches the sort inside one element, its "\"
    # dropped, and the sort writes that element back with a bare ";". The
    # loop then splits it into paths that can each name a listed file, none
    # of them the name that held the "\", so any "\;" in the glob's list is
    # listed as this one unhashed line instead.
    string(FIND "${paths}" "\\;" escaped)
    if(NOT escaped EQUAL -1)
        string(APPEND listing "unhashed a name holding \\ before a semicolon\n")
    endif()
    list(SORT paths)
    string(LENGTH "${SUITE}/" prefix_length)
    set(previous "")
    foreach(path IN LISTS paths)
        # The glob returns each path as it found it, where paths relative to
        # the suite would have "\" turned into "/" and ".." steps collapsed, so
        # that a name could arrive as another file's. A name holding ";"
        # arrives split at it, or whole where brackets enclose it. A "\" that
        # escaped a ";" in the glob's list is gone by here, and the check
        # before the sort has listed it; one that escapes a ";" the sort joined
        # is gone too, and leaves that ";" in its path. The piece before a
        # name's first ";" is cut from a path under directories the glob
        # walked, so it names nothing, a directory, or an entry the glob also
        # lists, which sorting puts beside it. A path not under the suite's
        # own, naming no file, holding ";" or "\", or repeating the one before
        # it is therefore listed unhashed rather than read, and every name
        # holding either character leaves at least one such line, here or
        # before the sort.
        string(SUBSTRING "${path}" 0 ${prefix_length} prefix)
        set(entry "${path}")
        if(prefix STREQUAL "${SUITE}/")
            string(SUBSTRING "${path}" ${prefix_length} -1 entry)
        endif()
        if(NOT prefix STREQUAL "${SUITE}/" OR IS_SYMLINK "${path}"
                OR IS_DIRECTORY "${path}" OR NOT EXISTS "${path}"
                OR entry MATCHES "[;\\]" OR path STREQUAL previous)
            string(APPEND listing "unhashed ${entry}\n")
        else()
            file(SHA256 "${path}" digest)
            string(APPEND listing "${digest}  ${entry}\n")
        endif()
        set(previous "${path}")
    endforeach()
    set(${OUT_VAR} "${listing}" PARENT_SCOPE)
endfunction()

# Function to download and extract test files
function(download_riscv_tests DOWNLOAD_PATH TARBALL_NAME DOWNLOAD_URL)
    # Checked even when an extracted tree is already present, so an enabled
    # suite always has recorded bytes to stand for.
    set(expected_sha256 "${TEST_DOWNLOAD_SHA256_${TEST_DOWNLOAD_VERSION}_${TARBALL_NAME}}")
    string(LENGTH "${expected_sha256}" expected_length)
    if(NOT expected_sha256 MATCHES "^[0-9a-f]+$" OR NOT expected_length EQUAL 64)
        message(FATAL_ERROR
            "No SHA-256 is recorded for ${TARBALL_NAME}.tar.gz at test release "
            "${TEST_DOWNLOAD_VERSION}: record the release asset's digest as "
            "TEST_DOWNLOAD_SHA256_${TEST_DOWNLOAD_VERSION}_${TARBALL_NAME} in "
            "${CMAKE_CURRENT_FUNCTION_LIST_FILE}")
    endif()

    # riscv_tests_listing finds the suite's files with a glob, which would read
    # [, ], * or ? in the suite's own path as a pattern and list files of
    # another tree, or none, and returns a list that would split every path
    # under the suite at a ";" in it.
    if(DOWNLOAD_PATH MATCHES "[][*?;]")
        message(FATAL_ERROR
            "The test download path ${DOWNLOAD_PATH} holds [, ], *, ? or ;, "
            "which the glob listing its suites would read as a pattern or split "
            "its paths at: configure in a build directory whose path has none "
            "of them")
    endif()

    # An extracted suite is kept only while its files are the ones its manifest
    # records for this digest, so a suite extracted before the manifest existed,
    # copied in without one, or changed since is removed and downloaded again.
    set(suite "${DOWNLOAD_PATH}/${TARBALL_NAME}")
    set(manifest "${suite}.manifest")
    if(EXISTS "${suite}" OR IS_SYMLINK "${suite}")
        set(recorded "")
        set(listing "unverified")
        if(EXISTS "${manifest}" AND IS_DIRECTORY "${suite}" AND NOT IS_SYMLINK "${suite}")
            file(READ "${manifest}" recorded)
            riscv_tests_listing("${suite}" "${TARBALL_NAME}" "${expected_sha256}" listing)
        endif()
        string(FIND "${listing}" "\nunhashed " unhashed)
        if(NOT recorded STREQUAL listing OR NOT unhashed EQUAL -1)
            message(STATUS "${TARBALL_NAME} has no matching ${TARBALL_NAME}.manifest, downloading again...")
            file(REMOVE_RECURSE "${suite}" "${manifest}")
        endif()
    endif()

    if(NOT EXISTS "${DOWNLOAD_PATH}/${TARBALL_NAME}")
        message(STATUS "${TARBALL_NAME}.tar.gz not extracted, downloading...")

        # Download the tar.gz file. A tarball left by an earlier run is kept
        # only if it already has the expected digest; otherwise it is fetched
        # again, and bytes that do not match fail the download.
        file(DOWNLOAD
            "${DOWNLOAD_URL}"
            "${DOWNLOAD_PATH}/${TARBALL_NAME}.tar.gz"
            SHOW_PROGRESS
            EXPECTED_HASH SHA256=${expected_sha256}
            STATUS download_status
        )

        # Check download status
        list(GET download_status 0 status_code)
        if(NOT status_code EQUAL 0)
            list(GET download_status 1 error_message)
            message(FATAL_ERROR "Failed to download ${TARBALL_NAME}: ${error_message}")
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

        # Record what the verified tarball extracted to, for the check above.
        riscv_tests_listing("${suite}" "${TARBALL_NAME}" "${expected_sha256}" listing)
        string(FIND "${listing}" "\nunhashed " unhashed)
        if(NOT unhashed EQUAL -1)
            message(FATAL_ERROR
                "${TARBALL_NAME}.tar.gz extracted a symbolic link or a name the "
                "listing cannot hash, which ${TARBALL_NAME}.manifest cannot record")
        endif()
        file(WRITE "${manifest}.partial" "${listing}")
        file(RENAME "${manifest}.partial" "${manifest}")

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
# and that is the in-tree assembler M1.4-prime extended to the backend's mix.
#
# What answers the question the set was asked is this repository's own pair, the
# model's `$[test]` harness (model/unit_tests/) and the differential corpus
# (corpus/), both of which are purecap programs against this machine rather than
# stock RISC-V programs against a machine it no longer is.

add_subdirectory("unit_tests")
