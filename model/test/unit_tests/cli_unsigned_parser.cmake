# Each child invokes the actual emulator parser. Check both conversion refusal
# and successfully returned values; accepting any nonzero exit would also accept
# an unrelated option error, a crash or a model initialization failure.
function(expect_value option value expected)
    execute_process(COMMAND "${PARSER}" "--${option}" "${value}"
        RESULT_VARIABLE result OUTPUT_VARIABLE output ERROR_VARIABLE error)
    string(FIND "${output}" "${option}=${expected}\n" found)
    if(NOT "${result}" STREQUAL "0" OR found EQUAL -1 OR NOT "${error}" STREQUAL "")
        message(FATAL_ERROR "${option}=${value}: expected ${expected}, exit=${result}\n${output}${error}")
    endif()
endfunction()

function(expect_conversion_refusal option value)
    execute_process(COMMAND "${PARSER}" "--${option}" "${value}"
        RESULT_VARIABLE result OUTPUT_VARIABLE output ERROR_VARIABLE error)
    string(FIND "${error}" "Could not convert: --${option} = ${value}" found)
    # CLI11's ConversionError exit code is 104. No post-parse field may print.
    if(NOT "${result}" STREQUAL "104" OR found EQUAL -1 OR NOT "${output}" STREQUAL "")
        message(FATAL_ERROR "${option}=${value}: expected conversion refusal, exit=${result}\n${output}${error}")
    endif()
endfunction()

foreach(option IN ITEMS inst-limit rot-slow-clock-ns stop-at-pc)
    foreach(value IN ITEMS 0 0b0 0B0 0o0 0O0 0x0)
        expect_value("${option}" "${value}" 0)
    endforeach()
    foreach(value IN ITEMS 21 +21 0b10101 0B10101 0o25 0O25 025 0x15 0X15)
        expect_value("${option}" "${value}" 21)
    endforeach()
    foreach(value IN ITEMS 18446744073709551615 0xffffffffffffffff 0o1777777777777777777777
            0b1111111111111111111111111111111111111111111111111111111111111111)
        expect_value("${option}" "${value}" 18446744073709551615)
    endforeach()
    foreach(value IN ITEMS -1 -0b1 -0B1 -0o1 -0O1 -01 -0x1 -0X1
            0b-1 0B-1 0o-1 0O-1 " -1" "0b -1" "0o\t-1"
            18446744073709551616 0x10000000000000000)
        expect_conversion_refusal("${option}" "${value}")
    endforeach()
endforeach()

# These unsigned options retain their existing positive/range validators.
expect_value(signature-granularity 4 4)
expect_value(signature-granularity 4294967295 4294967295)
foreach(option IN ITEMS rvfi-dii gdb-server-port)
    expect_value("${option}" 1 1)
    expect_value("${option}" 65535 65535)
endforeach()

message(STATUS "CLI unsigned parser: accepted values and conversion refusals passed")
