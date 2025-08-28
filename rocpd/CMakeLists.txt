cmake_minimum_required(VERSION 3.16)
project(rocpd-wheel NONE)

# Python versions to build wheels for (semicolon-separated list)
set(ROCPD_PYTHON_VERSIONS "3.10" CACHE STRING
    "Python versions to build rocpd wheels for")

set(ROCPD_VERSION "0.1.0")
set(ROCPD_SRC_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../rocpd")
set(ROCPD_STAGE_DIR "${CMAKE_CURRENT_BINARY_DIR}/rocpd_pkg")

file(REMOVE_RECURSE "${ROCPD_STAGE_DIR}")
file(MAKE_DIRECTORY "${ROCPD_STAGE_DIR}")
file(COPY "${ROCPD_SRC_DIR}" DESTINATION "${ROCPD_STAGE_DIR}")

# Write dummy C extension source to force a platlib wheel
file(WRITE "${ROCPD_STAGE_DIR}/marker_dummy.c" "int rocpd_marker(void){return 0;}\n")

# Write setup.py with dummy extension (no manual bdist options)
file(WRITE "${ROCPD_STAGE_DIR}/setup.py"
"from setuptools import setup, find_packages, Extension\n"
"ext_modules=[Extension('rocpd._marker', sources=['marker_dummy.c'])]\n"
"setup(\n"
"  name='rocpd',\n"
"  version='${ROCPD_VERSION}',\n"
"  packages=find_packages(),\n"
"  description='Minimal ROCpd Python interface with CTF support',\n"
"  python_requires='>=3.6',\n"
"  package_data={'rocpd': ['librocpd_barectf*.so', 'metadata']},\n"
"  include_package_data=True,\n"
"  ext_modules=ext_modules,\n"
")\n"
)

# Stage native artifacts
set(ROCPD_LIB_TARGET rocpd_barectf)
set(ROCPD_METADATA_SRC "${CMAKE_BINARY_DIR}/barectf/gen/metadata")
set(ROCPD_STAGED_LIB "${ROCPD_STAGE_DIR}/rocpd/librocpd_barectf.so")
set(ROCPD_STAGED_METADATA "${ROCPD_STAGE_DIR}/rocpd/metadata")

add_custom_command(OUTPUT ${ROCPD_STAGED_LIB}
  COMMAND ${CMAKE_COMMAND} -E copy $<TARGET_FILE:${ROCPD_LIB_TARGET}> ${ROCPD_STAGED_LIB}
  DEPENDS ${ROCPD_LIB_TARGET}
  COMMENT "Staging native library into wheel package")

add_custom_command(OUTPUT ${ROCPD_STAGED_METADATA}
  COMMAND ${CMAKE_COMMAND} -E copy_if_different ${ROCPD_METADATA_SRC} ${ROCPD_STAGED_METADATA}
  DEPENDS ${ROCPD_LIB_TARGET} ${ROCPD_METADATA_SRC}
  COMMENT "Staging metadata file into wheel package")

add_custom_target(rocpd_stage_assets DEPENDS ${ROCPD_STAGED_LIB} ${ROCPD_STAGED_METADATA})

set(WHEEL_TARGETS)
foreach(ver IN LISTS ROCPD_PYTHON_VERSIONS)
  string(REPLACE "." "" ver_nodot "${ver}")
  find_program(PYTHON_EXEC_${ver_nodot} NAMES "python${ver}" "python${ver}m" DOC "Python ${ver} interpreter")
  if(NOT PYTHON_EXEC_${ver_nodot})
    message(WARNING "Python ${ver} not found; skipping wheel for this version")
    continue()
  endif()
  set(dist_dir "${CMAKE_CURRENT_BINARY_DIR}/dist-${ver}")
  file(MAKE_DIRECTORY "${dist_dir}")
  add_custom_target(rocpd_wheel_${ver_nodot} ALL
    COMMAND "${PYTHON_EXEC_${ver_nodot}}" -m pip install --quiet --upgrade build setuptools wheel
    COMMAND "${PYTHON_EXEC_${ver_nodot}}" -m build --wheel --outdir "${dist_dir}"
    WORKING_DIRECTORY "${ROCPD_STAGE_DIR}"
    DEPENDS rocpd_stage_assets
    COMMENT "Building rocpd ${ROCPD_VERSION} wheel for Python ${ver}"
    VERBATIM)
  list(APPEND WHEEL_TARGETS rocpd_wheel_${ver_nodot})
endforeach()

if(WHEEL_TARGETS)
  add_custom_target(rocpd_wheels ALL DEPENDS ${WHEEL_TARGETS})
else()
  add_custom_target(rocpd_wheels ALL COMMENT "No matching Python versions were found; no wheels will be built.")
endif()

add_subdirectory(barectf)
