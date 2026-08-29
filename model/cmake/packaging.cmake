# Miscellaneous installation

# https://lintian.debian.org/tags/non-standard-dir-perm
set(CMAKE_INSTALL_DEFAULT_DIRECTORY_PERMISSIONS
    OWNER_READ OWNER_WRITE OWNER_EXECUTE
    GROUP_READ GROUP_EXECUTE
    WORLD_READ WORLD_EXECUTE
)

# https://lintian.debian.org/tags/no-copyright-file
install(FILES "${CMAKE_SOURCE_DIR}/LICENCE"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/doc/${CMAKE_PROJECT_NAME}"
    RENAME "copyright"
)
install(FILES "${CMAKE_SOURCE_DIR}/dependencies/softfloat/berkeley-softfloat-3/COPYING.txt"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/doc/${CMAKE_PROJECT_NAME}"
    RENAME "Berkeley-SoftFloat-LICENSE.txt"
)
install(FILES "${CMAKE_SOURCE_DIR}/dependencies/CLI11/LICENSE"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/doc/${CMAKE_PROJECT_NAME}"
    RENAME "CLI11-LICENSE.txt"
)
install(FILES "${CMAKE_SOURCE_DIR}/dependencies/elfio/LICENSE.txt"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/doc/${CMAKE_PROJECT_NAME}"
    RENAME "ELFIO-LICENSE.txt"
)
install(FILES "${CMAKE_SOURCE_DIR}/dependencies/jsoncons/LICENSE"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/doc/${CMAKE_PROJECT_NAME}"
    RENAME "JSONCONS-LICENSE.txt"
)
install(FILES "${CMAKE_SOURCE_DIR}/dependencies/asio/COPYING"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/doc/${CMAKE_PROJECT_NAME}"
    RENAME "ASIO-COPYRIGHT.txt"
)
# Don't rename this file since it is referred to by name in the
# asio/COPYING file.
install(FILES "${CMAKE_SOURCE_DIR}/dependencies/asio/LICENSE_1_0.txt"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/doc/${CMAKE_PROJECT_NAME}"
)

# No changelog is installed, and so lintian's `no-changelog` tag goes
# unanswered: `doc/` held upstream's account of releases of a model this tree is
# a curation of, and a changelog for the wrong artifact is worse than none.  The
# rule had to go with the file rather than be left to fail later, because the
# `file(ARCHIVE_CREATE)` that gzipped it ran at *configure*.

# CPack configuration

if (NOT CPACK_GENERATOR)
    if (WINDOWS)
        set(CPACK_GENERATOR "ZIP")
    else()
        set(CPACK_GENERATOR "TGZ")
    endif()
endif()

if (APPLE)
    # ${CMAKE_SYSTEM_NAME} is unfortunately "Darwin", but we want "Mac".
    set(CPACK_PACKAGE_FILE_NAME "${CMAKE_PROJECT_NAME}-Mac-${CMAKE_HOST_SYSTEM_PROCESSOR}")
else()
    set(CPACK_PACKAGE_FILE_NAME "${CMAKE_PROJECT_NAME}-${CMAKE_SYSTEM_NAME}-${CMAKE_HOST_SYSTEM_PROCESSOR}")
endif()

set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Sail RISC-V Model")
set(CPACK_PACKAGE_DESCRIPTION "A formal specification of the RISC-V architecture written in Sail.")
set(CPACK_PACKAGE_VENDOR "RISC-V International")
set(CPACK_PACKAGE_CONTACT "prashanth@riscv.org")

# https://lintian.debian.org/tags/unstripped-binary-or-object
set(CPACK_STRIP_FILES TRUE)

# Settings for DEB.
set(CPACK_DEBIAN_PACKAGE_MAINTAINER "Prashanth Mundkur <${CPACK_PACKAGE_CONTACT}>")
set(CPACK_DEBIAN_FILE_NAME DEB-DEFAULT)
set(CPACK_DEBIAN_PACKAGE_SHLIBDEPS TRUE)

# Settings for RPM.
set(CPACK_RPM_FILE_NAME RPM-DEFAULT)
set(CPACK_RPM_PACKAGE_DESCRIPTION ${CPACK_PACKAGE_DESCRIPTION})
set(CPACK_RPM_PACKAGE_LICENSE "BSD-2-Clause")
set(CPACK_RPM_PACKAGE_AUTOREQ TRUE)

include(CPack)
