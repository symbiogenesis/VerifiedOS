# Sail unit tests. Currently this only runs the default config (RV64D).

add_executable(unit_tests
    "main_unit_tests.cpp"
)

target_link_libraries(unit_tests
    PRIVATE riscv_model default_config
)

add_test(
    NAME "unit_tests"
    COMMAND $<TARGET_FILE:unit_tests>
)

add_executable(entropy_observer "entropy_observer.cpp")
target_link_libraries(entropy_observer PRIVATE riscv_model default_config)
add_test(NAME "entropy_observer" COMMAND $<TARGET_FILE:entropy_observer>)

add_executable(block_payload "block_payload.cpp")
target_link_libraries(block_payload PRIVATE riscv_model default_config)
add_test(NAME "block_payload" COMMAND $<TARGET_FILE:block_payload>)
add_test(NAME "block_payload_wrong_expected_byte"
    COMMAND $<TARGET_FILE:block_payload> --wrong-expected-byte)
set_tests_properties(block_payload_wrong_expected_byte PROPERTIES WILL_FAIL TRUE)

add_executable(watchdog_join "watchdog_join.cpp")
target_link_libraries(watchdog_join PRIVATE riscv_model default_config)
add_test(NAME "watchdog_join" COMMAND $<TARGET_FILE:watchdog_join>)

# The two inverted expectations. These are registered by the assertion each one
# must reach rather than with WILL_FAIL, which accepts any nonzero exit and so
# would record a crash, or the usage error this harness returns for an
# unrecognized argument, as the expected failure. PASS_REGULAR_EXPRESSION
# requires the intended message, and FAIL_REGULAR_EXPRESSION refuses the success
# line, so a run that both printed the message and claimed to pass is a failure.
add_test(NAME "watchdog_join_retirement_bites"
    COMMAND $<TARGET_FILE:watchdog_join> --negative-retirement-bites)
set_tests_properties(watchdog_join_retirement_bites PROPERTIES
    PASS_REGULAR_EXPRESSION "watchdog join: FAIL no external clock: retirement alone moved the watchdog"
    FAIL_REGULAR_EXPRESSION "watchdog join: window=")
add_test(NAME "watchdog_join_no_reset" COMMAND $<TARGET_FILE:watchdog_join> --negative-no-reset)
set_tests_properties(watchdog_join_no_reset PROPERTIES
    PASS_REGULAR_EXPRESSION
        "watchdog join: FAIL stopped main clock: the bite did not assert the die reset with the core stopped"
    FAIL_REGULAR_EXPRESSION "watchdog join: window=")

add_executable(block_reset "block_reset.cpp")
target_link_libraries(block_reset PRIVATE riscv_model default_config)
add_test(NAME "block_reset" COMMAND $<TARGET_FILE:block_reset>)
add_test(NAME "block_reset_wrong_byte" COMMAND $<TARGET_FILE:block_reset> --negative-byte)
add_test(NAME "block_reset_residual_volatile" COMMAND $<TARGET_FILE:block_reset> --negative-volatile)
set_tests_properties(block_reset_wrong_byte block_reset_residual_volatile PROPERTIES WILL_FAIL TRUE)

# M5.3d: the host backing image across process exit, and the emulator's own
# image options. The inverted expectations are registered by the comparison
# each must reach, as watchdog_join's are, so a crash or a usage error cannot
# pass as the expected failure.
add_executable(block_image "block_image.cpp")
target_link_libraries(block_image PRIVATE riscv_model default_config)
add_test(NAME "block_image" COMMAND $<TARGET_FILE:block_image> --emulator $<TARGET_FILE:sail_riscv_sim>)
add_test(NAME "block_image_wrong_byte" COMMAND $<TARGET_FILE:block_image> --negative-byte)
add_test(NAME "block_image_reloaded_fixture" COMMAND $<TARGET_FILE:block_image> --negative-reload-fixture)
set_tests_properties(block_image_wrong_byte PROPERTIES
    PASS_REGULAR_EXPRESSION "block image child: FAIL reopened medium byte 0 expected"
    FAIL_REGULAR_EXPRESSION "block image: B=")
set_tests_properties(block_image_reloaded_fixture PROPERTIES
    PASS_REGULAR_EXPRESSION "block image child: FAIL reopened medium byte [0-9]+ expected"
    FAIL_REGULAR_EXPRESSION "block image: B=")

# Receipt sink failures can be reproduced without rebuilding generated Sail.
add_executable(block_receipt "block_receipt.cpp" "../../c_emulator/blkdev_image.cpp")
target_include_directories(block_receipt PRIVATE "../../c_emulator")
add_test(NAME "block_receipt" COMMAND $<TARGET_FILE:block_receipt>)
