# SPDX-License-Identifier: Apache-2.0
# Recheck bytes at every build. Ninja's restat keeps unchanged identity from
# invalidating generation, including when an installer preserves file mtimes.
function(sail_add_toolchain_identity)
    set(SAIL_TOOLCHAIN_STAMP "${CMAKE_BINARY_DIR}/sail_toolchain.sha256" PARENT_SCOPE)
    add_custom_target(generated_sail_toolchain
        COMMAND "${CMAKE_COMMAND}"
            "-DSAIL_BIN=${SAIL_BIN}"
            "-DSAIL_LIBRARY_DIR=${sail_dir}"
            "-DSAIL_LOADER_IDENTITY=${VOS_SAIL_LOADER_IDENTITY}"
            "-DSAIL_IDENTITY_STAMP=${CMAKE_BINARY_DIR}/sail_toolchain.sha256"
            -P "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/sail_toolchain_identity.cmake"
        BYPRODUCTS "${CMAKE_BINARY_DIR}/sail_toolchain.sha256"
        COMMENT "Checking Sail generator input identity"
        VERBATIM
    )
endfunction()

# A successful input fingerprint is not evidence of successful generation.
# Remove the completion stamp before starting; partial files from a failed
# generator cannot satisfy the next build even when their timestamps are new.
function(sail_generated_command)
    cmake_parse_arguments(PARSE_ARGV 0 GENERATE ""
        "STAMP;COMMENT;WORKING_DIRECTORY" "OUTPUTS;DEPENDS;COMMAND")
    if(GENERATE_UNPARSED_ARGUMENTS OR GENERATE_KEYWORDS_MISSING_VALUES
            OR NOT GENERATE_STAMP OR NOT GENERATE_COMMAND)
        message(FATAL_ERROR "sail_generated_command requires a stamp and command")
    endif()
    set(byproducts)
    if(GENERATE_OUTPUTS)
        set(byproducts BYPRODUCTS ${GENERATE_OUTPUTS})
    endif()
    add_custom_command(
        OUTPUT "${GENERATE_STAMP}"
        ${byproducts}
        DEPENDS generated_sail_toolchain "${SAIL_TOOLCHAIN_STAMP}" ${GENERATE_DEPENDS}
        COMMAND "${CMAKE_COMMAND}" -E rm -f "${GENERATE_STAMP}"
        COMMAND ${GENERATE_COMMAND}
        COMMAND "${CMAKE_COMMAND}" -E touch "${GENERATE_STAMP}"
        WORKING_DIRECTORY "${GENERATE_WORKING_DIRECTORY}"
        COMMENT "${GENERATE_COMMENT}"
        VERBATIM
    )
endfunction()
