include(FetchContent)

FetchContent_Declare(
  asio
  URL https://github.com/chriskohlhoff/asio/archive/refs/tags/asio-1-38-2.tar.gz
  URL_HASH SHA3_256=5ea1dd86c63a2d5ab87ab20ff24992d2e1aaba327363d68966552482f60da1a1
)

# Allow downloads to be turned off (in particular, for targets that don't need it).
option(DOWNLOAD_ASIO "Download asio" ON)

if (DOWNLOAD_ASIO)
  FetchContent_MakeAvailable(asio)

  add_library(asio INTERFACE
      "${asio_SOURCE_DIR}/include/asio.hpp"
  )
  target_include_directories(asio INTERFACE
      "${asio_SOURCE_DIR}/include"
  )
  target_compile_definitions(asio INTERFACE
      -DASIO_NO_DEPRECATED
  )

  # On Rocky Linux 8.9, the build fails unless linked with -pthread.
  set(THREADS_PREFER_PTHREAD_FLAG TRUE)
  find_package(Threads)
  target_link_libraries(asio INTERFACE Threads::Threads)
endif()
