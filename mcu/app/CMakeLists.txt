cmake_minimum_required(VERSION 3.20.0)

# Register the bundled libmicroros as an extra Zephyr module. Must be set
# before find_package(Zephyr). The path resolves from this app/ directory
# up to the workspace topdir and into the cloned micro-ROS module repo.
list(APPEND ZEPHYR_EXTRA_MODULES
  ${CMAKE_CURRENT_SOURCE_DIR}/../modules/micro_ros_zephyr_module/modules/libmicroros)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(havoc_mcu)

target_sources(app PRIVATE src/main.c)
