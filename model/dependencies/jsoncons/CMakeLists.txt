include(FetchContent)

# Allow downloads to be turned off (in particular, for targets that don't need it).
option(DOWNLOAD_JSONCONS "Download jsoncons" ON)

# The jsoncons `unit_tests` target conflicts with our own.
set(JSONCONS_BUILD_TESTS OFF)

FetchContent_Declare(
  jsoncons
  URL https://github.com/danielaparker/jsoncons/archive/refs/tags/v1.9.0.tar.gz
  URL_HASH SHA3_256=1c073edb95951f3090d9f91e2f684a0122fc40a8648542ffca62e9b913e6a128
)

if (DOWNLOAD_JSONCONS)
    FetchContent_MakeAvailable(jsoncons)

    set_target_properties(jsoncons
        PROPERTIES SKIP_LINTING ON
    )
endif()
