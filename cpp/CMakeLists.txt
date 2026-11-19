cmake_minimum_required(VERSION 3.16)

# Single source of truth: the version comes from src/chronus/__init__.py (chronus.__version__).
# Registered as a configure dependency so a version-only edit re-runs configuration.
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/../src/chronus/__init__.py")
file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/../src/chronus/__init__.py" _chronus_version_line
     REGEX "^__version__ = \"[^\"]+\"")
string(REGEX REPLACE "^__version__ = \"([^\"]+)\".*" "\\1" CHRONUS_VERSION "${_chronus_version_line}")
string(REGEX MATCH "^[0-9]+\\.[0-9]+\\.[0-9]+" CHRONUS_VERSION_NUMERIC "${CHRONUS_VERSION}")
if(NOT CHRONUS_VERSION_NUMERIC)
    message(FATAL_ERROR "Could not read chronus.__version__ from src/chronus/__init__.py")
endif()

project(chronus_igpu_native VERSION ${CHRONUS_VERSION_NUMERIC} LANGUAGES C CXX)
add_compile_definitions(CHRONUS_VERSION_STRING="${CHRONUS_VERSION}")

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
