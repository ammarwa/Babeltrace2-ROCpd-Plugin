cmake_minimum_required(VERSION 3.13)
project(rocpd_barectf LANGUAGES C)

set(PLATFORM_DIR "${CMAKE_CURRENT_SOURCE_DIR}/barectf-platform-linux-fs" CACHE PATH "Path to the barectf Linux FS platform implementation")
set(GEN_DIR "${CMAKE_CURRENT_BINARY_DIR}/gen" CACHE PATH "Directory to contain generated barectf sources")

file(MAKE_DIRECTORY "${GEN_DIR}")

# Custom command to generate code with barectf
add_custom_command(
    OUTPUT "${GEN_DIR}/barectf.c"
    COMMAND barectf gen -c "${GEN_DIR}" -H "${GEN_DIR}" -m "${GEN_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/rocpd.yaml"
    DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/rocpd.yaml"
    COMMENT "Generating barectf sources"
)

# Custom target that wraps the generation command
add_custom_target(gen_barectf DEPENDS "${GEN_DIR}/barectf.c")

# Shared library sources
set(SRCS
    "${CMAKE_CURRENT_SOURCE_DIR}/rocpd_bridge.c"
    "${PLATFORM_DIR}/barectf-platform-linux-fs.c"
    "${GEN_DIR}/barectf.c"
)

# Define the library and its properties
add_library(rocpd_barectf SHARED ${SRCS})
target_include_directories(rocpd_barectf PRIVATE "${GEN_DIR}" "${PLATFORM_DIR}")
target_compile_options(rocpd_barectf PRIVATE -O2)

# Ensure the library is built after generating code
add_dependencies(rocpd_barectf gen_barectf)

# Install rule, optional: place the shared library into lib.
install(TARGETS rocpd_barectf
        LIBRARY DESTINATION lib)

install(FILES "${GEN_DIR}/metadata"
        DESTINATION share)
