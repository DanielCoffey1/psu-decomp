# psu - ReXGlue Recompiled Project
#
# SDK boilerplate lives in generated/rexglue.cmake.

cmake_minimum_required(VERSION 3.25)
project(psu LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(generated/rexglue.cmake)

# Sources
set(PSU_SOURCES
    src/main.cpp
    src/keyboard_taps.cpp
    src/runtime_trace.cpp
    src/extra_mode.cpp
)

if(WIN32)
    add_executable(psu WIN32 ${PSU_SOURCES})
else()
    add_executable(psu ${PSU_SOURCES})
endif()

option(PSU_STAGE_BINARY "Build a separate executable while the game is running" OFF)
if(PSU_STAGE_BINARY)
    set_target_properties(psu PROPERTIES OUTPUT_NAME psu-staged)
endif()

rexglue_setup_target(psu GPU_PLUGINS xenos)
