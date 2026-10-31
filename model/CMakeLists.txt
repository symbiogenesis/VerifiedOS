cmake_minimum_required(VERSION 3.26)
cmake_policy(VERSION 3.26...3.31)

# This sets -mmacosx-version-min. It must be done before project() (see the CMake docs).
set (CMAKE_OSX_DEPLOYMENT_TARGET 10.15)

include(cmake/project_version.cmake)
project(sail-riscv
  VERSION ${sail_riscv_release_version}
  HOMEPAGE_URL "https://github.com/riscv/sail-riscv"
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED TRUE)
include(cmake/sail_required_version.cmake)

# Make users explicitly pick a build type so they don't get
# surprised when the default gives a very slow emulator.
if (NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    message(FATAL_ERROR "
No build type selected. You need to pass -DCMAKE_BUILD_TYPE=<type> in order to configure the build.
    * -DCMAKE_BUILD_TYPE=Release        - Optimized build with no debug info.
    * -DCMAKE_BUILD_TYPE=RelWithDebInfo - Optimized build with debug info.
    * -DCMAKE_BUILD_TYPE=Debug          - Unoptimized build with debug info.
    * -DCMAKE_BUILD_TYPE=MinSizeRel     - Optimized for size instead of speed.")
endif()

# Enable CTest
enable_testing()

# Export compile_commands.json for IDE support.
set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)

# Always use Position Independent Code. By default it is only used for
# shared libraries (which require it), but you also need it for static
# libraries if you link them into shared libraries.
# Generally it just simplifies everything for a negligible performance cost.
set(CMAKE_POSITION_INDEPENDENT_CODE TRUE)

# Enable clang-tidy.
option(ENABLE_CLANG_TIDY "Enable clang-tidy linting." OFF)
if (ENABLE_CLANG_TIDY)
    find_program(CLANG_TIDY_PATH clang-tidy REQUIRED)
endif()

# Enable link-time optimization globally. This allows the linker to inline
# Sail runtime helpers (eq_bits, add_bits_int, etc.) into the generated
# model code, which is the dominant cost in the simulator hot path.
# Disabled by default because it can make compile times worse.
option(ENABLE_LTO "Enable link-time optimization" FALSE)
if (ENABLE_LTO)
    include(CheckIPOSupported)
    check_ipo_supported(RESULT lto_supported OUTPUT lto_error)
    if (lto_supported)
        set(CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE)
        message(STATUS "LTO enabled")
    else()
        message(FATAL_ERROR "LTO requested but not supported: ${lto_error}")
    endif()
endif()

# First-party build settings do not leak into fetched dependency projects.
add_library(sail_assertions INTERFACE)
add_library(sail_build_options INTERFACE)
target_link_libraries(sail_build_options INTERFACE sail_assertions)

# Don't allow undefined symbols. This is generally a pain.
include(CheckLinkerFlag)

check_linker_flag(C "-Wl,--no-undefined" LINKER_SUPPORTS_NO_UNDEFINED)
if (LINKER_SUPPORTS_NO_UNDEFINED)
    target_link_options(sail_build_options INTERFACE "-Wl,--no-undefined")
endif()

target_compile_options(sail_build_options INTERFACE -Wall -Wextra -Wno-sign-compare)
include(CheckCCompilerFlag)
check_c_compiler_flag(-Wimplicit-fallthrough HAVE_WIMPLICIT_FALLTHROUGH)

# Ensure model, runtime and test targets build with assertions enabled in non-Debug
# builds, following the approach of LLVM in
#   llvm/cmake/modules/HandleLLVMOptions.cmake
string(TOUPPER "${CMAKE_BUILD_TYPE}" uppercase_CMAKE_BUILD_TYPE)
# On non-Debug builds cmake automatically defines NDEBUG; so
# explicitly undefine it:
if(NOT uppercase_CMAKE_BUILD_TYPE STREQUAL "DEBUG")
    target_compile_options(sail_assertions INTERFACE
        $<$<OR:$<COMPILE_LANGUAGE:C>,$<COMPILE_LANGUAGE:CXX>>:-UNDEBUG>)
endif()

# Extra CMake files.
set(CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake/modules")

# This will change how the `find_library` calls work so they find
# the static version of libraries first. Unlike `-static` it won't
# link glibc statically, which is generally considered to be a bad idea.
option(STATIC "Prefer static versions of dependencies.")

if (STATIC)
    if (WIN32)
        list(INSERT CMAKE_FIND_LIBRARY_SUFFIXES 0 .lib .a)
    else()
        set(CMAKE_FIND_LIBRARY_SUFFIXES .a)

        check_linker_flag(CXX "-static-libstdc++" HAVE_STATIC_LIBSTDCXX)
        if (HAVE_STATIC_LIBSTDCXX)
            target_link_options(sail_build_options INTERFACE -static-libstdc++)
        endif()

        check_linker_flag(CXX "-static-libgcc" HAVE_STATIC_LIBGCC)
        if (HAVE_STATIC_LIBGCC)
            target_link_options(sail_build_options INTERFACE -static-libgcc)
        endif()
    endif()
endif()


# These are the main requirements.
# Don't use `REQUIRED` so that we can print custom help messages.
option(DOWNLOAD_GMP "Download libgmp and build the library locally instead of using a system installation" OFF)
if (DOWNLOAD_GMP)
    include(ExternalProject)
    # Build GMP with LTO when ENABLE_LTO is on, using the same toolchain and
    # IPO flags as the main project so the LTO bytecode is compatible.
    if (ENABLE_LTO)
        list(JOIN CMAKE_C_COMPILE_OPTIONS_IPO " " GMP_LTO_CFLAGS)
        list(JOIN CMAKE_C_LINK_OPTIONS_IPO " " GMP_LTO_LDFLAGS)
        set(GMP_EXTRA_CONFIGURE_ARGS
            "CFLAGS=-std=c11 -O3 ${GMP_LTO_CFLAGS}"
            "LDFLAGS=${GMP_LTO_LDFLAGS}"
            "CC=${CMAKE_C_COMPILER}"
            "CXX=${CMAKE_CXX_COMPILER}"
        )
    else()
        set(GMP_EXTRA_CONFIGURE_ARGS "CFLAGS=-std=c11")
    endif()
    ExternalProject_Add(
        gmp
        URL https://ftp.gnu.org/gnu/gmp/gmp-6.3.0.tar.xz https://gmplib.org/download/gmp/gmp-6.3.0.tar.xz https://ftpmirror.gnu.org/gnu/gmp/gmp-6.3.0.tar.xz
        URL_HASH SHA256=a3c2b80201b89e68616f4ad30bc66aee4927c3ce50e33929ca819d5c43538898
        # Preserve only GMP's archive mtimes: its generated documentation would
        # otherwise be rebuilt with makeinfo. Other archives use CMP0135 NEW.
        DOWNLOAD_EXTRACT_TIMESTAMP TRUE
        INSTALL_DIR ${CMAKE_CURRENT_BINARY_DIR}/gmp
        CONFIGURE_COMMAND "<SOURCE_DIR>/configure"
            "--prefix=<INSTALL_DIR>"
            --disable-shared
            --enable-static
            --with-pic
            # Newer compilers default to C23 which causes GMP build errors.
            ${GMP_EXTRA_CONFIGURE_ARGS}
        INSTALL_BYPRODUCTS "<INSTALL_DIR>/lib/libgmp.a"
    )

    ExternalProject_Get_property(gmp INSTALL_DIR)
    add_library(GMP::GMP STATIC IMPORTED GLOBAL)
    # Work around `Imported target "GMP::GMP" includes non-existent path`.
    # See https://gitlab.kitware.com/cmake/cmake/-/issues/15052
    file(MAKE_DIRECTORY ${INSTALL_DIR}/include)
    set_target_properties(GMP::GMP PROPERTIES
            IMPORTED_LOCATION "${INSTALL_DIR}/lib/libgmp.a"
            INTERFACE_INCLUDE_DIRECTORIES "${INSTALL_DIR}/include")
    add_dependencies(GMP::GMP gmp)
else()
    find_package(GMP)
    if (NOT GMP_FOUND)
        set(download_gmp "setting -DDOWNLOAD_GMP=TRUE to use a local build of GMP instead of a system library")
        if (APPLE)
            message(FATAL_ERROR "GMP not found. Try 'brew install gmp' or ${download_gmp}.")
        elseif (UNIX)
            message(FATAL_ERROR "GMP not found. Try 'sudo apt install libgmp-dev' or 'sudo dnf install gmp-devel' or ${download_gmp}.")
        else()
            message(FATAL_ERROR "GMP not found. Try ${download_gmp}")
        endif()
    endif()
endif()

find_program(SAIL_BIN "sail")
if (NOT SAIL_BIN)
    message(FATAL_ERROR "Sail not found. See README.md for installation instructions.")
endif()
message(STATUS "Found sail: ${SAIL_BIN}")

# Set sail_dir to Sail's library directory for use in build rules
execute_process(
    COMMAND ${SAIL_BIN} --dir
    OUTPUT_VARIABLE sail_dir
    OUTPUT_STRIP_TRAILING_WHITESPACE
    COMMAND_ERROR_IS_FATAL ANY
)
message(STATUS "Sail library directory: ${sail_dir}")

include(cmake/sail_toolchain.cmake)
sail_add_toolchain_identity()

option(COVERAGE "Compile with Sail coverage collection enabled.")

include(GNUInstallDirs)

# Third party dependencies.
add_subdirectory("dependencies")

# Sail C runtime.
add_subdirectory("sail_runtime")

# Sail configuration
add_subdirectory("config")

# Sail model generated C code.
add_subdirectory("model")

# Emulator binary.
add_subdirectory("c_emulator")

# Old pre-compiled riscv-tests & first-party tests.
add_subdirectory("test")

# Handwritten support files for provers
add_subdirectory("handwritten_support")

# Apply warnings and link settings only to model/runtime/test code. SoftFloat
# keeps assertion behavior without inheriting first-party warning policy.
function(sail_apply_build_options directory)
    get_property(targets DIRECTORY "${directory}" PROPERTY BUILDSYSTEM_TARGETS)
    foreach(target IN LISTS targets)
        get_target_property(kind "${target}" TYPE)
        if(kind MATCHES "^(EXECUTABLE|STATIC_LIBRARY|SHARED_LIBRARY|OBJECT_LIBRARY)$")
            target_link_libraries("${target}" PRIVATE sail_build_options)
        endif()
    endforeach()
    get_property(children DIRECTORY "${directory}" PROPERTY SUBDIRECTORIES)
    foreach(child IN LISTS children)
        sail_apply_build_options("${child}")
    endforeach()
endfunction()
sail_apply_build_options("${CMAKE_CURRENT_SOURCE_DIR}/sail_runtime")
sail_apply_build_options("${CMAKE_CURRENT_SOURCE_DIR}/c_emulator")
sail_apply_build_options("${CMAKE_CURRENT_SOURCE_DIR}/test")
target_link_libraries(softfloat PRIVATE sail_assertions)

# Convenience targets.
add_custom_target(csim DEPENDS sail_riscv_sim)
add_custom_target(check DEPENDS generated_model_rv)

# TODO: Add `interpret` target.

# Release packaging.
include(cmake/packaging.cmake)
