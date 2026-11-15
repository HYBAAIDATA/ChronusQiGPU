cmake_minimum_required(VERSION 3.16)
project(chronus_igpu_native VERSION 36.0.1 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Optimization flags and architecture features
if(MSVC)
    add_compile_options(/O2 /W4 /arch:AVX2)
else()
    add_compile_options(-O3 -Wall -Wextra -mavx2 -mfma)
endif()

include_directories(include)

set(SOURCES
    src/igpu_simd.cpp
    src/quantum_superposition.cpp
    src/exact_lattice.cpp
    src/c_api.cpp
)

# Shared library for Python ctypes/C-ABI binding
add_library(chronus_igpu SHARED ${SOURCES})

target_include_directories(chronus_igpu PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

target_compile_definitions(chronus_igpu PRIVATE CHRONUS_BUILD_DLL)

# Set output directory to project bin or lib
set_target_properties(chronus_igpu PROPERTIES
    PREFIX "lib"
    OUTPUT_NAME "chronus_igpu"
)
