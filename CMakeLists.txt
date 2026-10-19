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
)

if(WIN32)
    add_executable(psu WIN32 ${PSU_SOURCES})
else()
    add_executable(psu ${PSU_SOURCES})
endif()

rexglue_setup_target(psu GPU_PLUGINS xenos)
