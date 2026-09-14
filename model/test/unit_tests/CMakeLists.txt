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
