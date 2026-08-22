set(generated_config_filenames)

# Create a variety of configuration files for different ELEN/VLENs. XLEN is
# not among them: the base is RV64 and RV32 is not a configuration of this
# model (model/core/xlen.sail), so the file names keep their `rv64` stem and
# the knob behind it is gone.
foreach(CONFIG__V__ELEN_EXP RANGE 5 6)
    foreach(CONFIG__V__VLEN_EXP RANGE 6 9)
        math(EXPR vlen "1 << ${CONFIG__V__VLEN_EXP}")
        math(EXPR elen "1 << ${CONFIG__V__ELEN_EXP}")

        set(config_filename "rv64d_v${vlen}_e${elen}.json")

        set(CONFIG_ELEN_IS_32 "false")
        set(CONFIG_ELEN_IS_64 "false")
        set(CONFIG_ELEN_IS_${elen} "true")

        if(CONFIG_ELEN_IS_32 STREQUAL true)
          set(CONFIG__V__SUPPORT "Float_single")
        # Check if we can enable the full V extension.
        elseif((CONFIG_ELEN_IS_64 STREQUAL true) AND (vlen GREATER 64))
          set(CONFIG__V__SUPPORT "Full")
        # Otherwise fallback to Float_double for ELEN=64.
        elseif(CONFIG_ELEN_IS_64 STREQUAL true)
          set(CONFIG__V__SUPPORT "Float_double")
        endif()

        set(CONFIG__PHYSADDR__BITS 56)

        # The C row's Keccak unit follows the geometry this configuration is
        # generated at. The frozen permutation is one instruction over a
        # 2048-bit element group of 32 SEW=64 elements and a vector register
        # group tops out at LMUL=8, so the unit needs ELEN=64 and VLEN >= 256;
        # below either, a row declaring it describes a datapath whose one
        # instruction can never decode, which the validator refuses
        # (model/postlude/validate_config.sail, R-15-056, R-15-057a).
        if((CONFIG__V__ELEN_EXP GREATER_EQUAL 6) AND (CONFIG__V__VLEN_EXP GREATER_EQUAL 8))
            set(CONFIG__KECCAK_UNIT "true")
        else()
            set(CONFIG__KECCAK_UNIT "false")
        endif()

        configure_file(config.json.in ${CMAKE_CURRENT_BINARY_DIR}/${config_filename})

        install(FILES ${CMAKE_CURRENT_BINARY_DIR}/${config_filename}
            DESTINATION ${CMAKE_INSTALL_DATADIR}/${CMAKE_PROJECT_NAME}/config
        )

        list(APPEND generated_config_filenames "${CMAKE_CURRENT_BINARY_DIR}/${config_filename}")
    endforeach()
endforeach()

# Make list of config files visible to c_emulator build.
set(generated_config_filenames "${generated_config_filenames}" PARENT_SCOPE)

# Embed the default config in a C header.
file(READ "${CMAKE_CURRENT_BINARY_DIR}/rv64d_v256_e64.json" DEFAULT_JSON)
configure_file("default_config.h.in" "default_config.h" @ONLY)

add_library(default_config INTERFACE
    "default_config.h"
)

target_include_directories(default_config INTERFACE "${CMAKE_CURRENT_BINARY_DIR}")
