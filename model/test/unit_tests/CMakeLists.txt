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
