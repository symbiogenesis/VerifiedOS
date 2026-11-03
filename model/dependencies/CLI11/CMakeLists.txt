include(FetchContent)

# Allow downloads to be turned off (in particular, for targets that don't need it).
option(DOWNLOAD_CLI11 "Download CLI11" ON)

FetchContent_Declare(cli11
  # PR 1472: reject negative unsigned payloads after binary/octal prefixes.
  URL "https://codeload.github.com/CLIUtils/CLI11/tar.gz/1764a057b760e8873eab03f4635b4aaed5303a04"
  URL_HASH SHA256=6fa7a14f662be8461af1c1d3cf8f7a56b99492067127c986fdc9ec0dbd4f3e6a
)

if(DOWNLOAD_CLI11)
  if(VOS_MODEL_OFFLINE AND NOT IS_DIRECTORY "${FETCHCONTENT_SOURCE_DIR_CLI11}")
    message(FATAL_ERROR "Offline CLI11 input is missing; run model dependencies first")
  endif()
  FetchContent_MakeAvailable(cli11)
endif()
