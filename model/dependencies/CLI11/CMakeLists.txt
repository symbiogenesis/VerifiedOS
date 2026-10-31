include(FetchContent)

# Allow downloads to be turned off (in particular, for targets that don't need it).
option(DOWNLOAD_CLI11 "Download CLI11" ON)

FetchContent_Declare(cli11
  # PR 1472: reject negative unsigned payloads after binary/octal prefixes.
  URL "https://codeload.github.com/CLIUtils/CLI11/tar.gz/08ca3298f6704bfe652f5b85e1bc22dc2800ac5f"
  URL_HASH SHA256=ef660e648ec74b4449db1e958767836c28c43f34f3d8184e182b4c8d5bd1422b
)

if(DOWNLOAD_CLI11)
  if(VOS_MODEL_OFFLINE AND NOT IS_DIRECTORY "${FETCHCONTENT_SOURCE_DIR_CLI11}")
    message(FATAL_ERROR "Offline CLI11 input is missing; run model dependencies first")
  endif()
  FetchContent_MakeAvailable(cli11)
endif()
