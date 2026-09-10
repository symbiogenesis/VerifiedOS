include(FetchContent)

# Allow downloads to be turned off (in particular, for targets that don't need it).
option(DOWNLOAD_CLI11 "Download CLI11" ON)

FetchContent_Declare(cli11_hpp
  URL "https://github.com/CLIUtils/CLI11/releases/download/v2.7.2/CLI11.hpp"
  DOWNLOAD_NO_EXTRACT YES
  URL_HASH SHA256=ffa9a30da295c5858fb5f91f9f45771bab09471d7010a34c7c68c857a330dd76
)

if(DOWNLOAD_CLI11)
  FetchContent_MakeAvailable(cli11_hpp)
  add_library(CLI11 INTERFACE)
  target_include_directories(CLI11
    SYSTEM INTERFACE
    "${cli11_hpp_SOURCE_DIR}")
endif()
