# Increment this appropriately at tag-and-release time.
set(sail_riscv_release_version "0.13.1")

# Sets GIT_EXECUTABLE
find_package(Git)

if (Git_FOUND)
  # --tags     Search for lightweight tags as well as annotated ones.
  # --always   If there are no tags use the git hash instead of failing.
  # --dirty    Append '-dirty' if the working tree has local modifications.
  # --broken   Append '-broken' if the repo is corrupt instead of failing.
  #
  # WORKING_DIRECTORY is this file's own tree and not the build's. Without it
  # `execute_process` runs in the current binary directory, which for an
  # out-of-tree build is not a git repository at all, so `git describe` exits
  # 128 and the emulator reports itself as "unknown commit". That is a
  # cosmetic defect upstream, where builds are usually in-tree, and a
  # load-bearing one here: this emulator is the executable ISA reference every
  # downstream artifact is stated against, and a reference that cannot name
  # which model it is cannot supply the model revision a freeze report is
  # required to carry beside its cycle columns.
  execute_process(
    COMMAND ${GIT_EXECUTABLE} describe --tags --always --dirty --broken
    WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
    RESULT_VARIABLE git_error
    OUTPUT_VARIABLE git_describe
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )
else()
  set(git_error TRUE)
endif()

if (git_error)
  message(STATUS "Failed to run git describe: ${git_error}")
  set(sail_riscv_git_version   "unknown commit")
else()
  set(sail_riscv_git_version   ${git_describe})
endif()

# Log versions in the build log.
message(STATUS "Building versions: ${sail_riscv_git_version} (git), ${sail_riscv_release_version} (cmake).")
