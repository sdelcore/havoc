cmake_minimum_required(VERSION 3.8)
project(havoc_description)

find_package(ament_cmake REQUIRED)

install(DIRECTORY urdf launch config worlds rviz
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_launches test/test_launches.py
    TIMEOUT 60
  )
  # Full E2E: launches Gazebo + bridge + RTAB-Map, drives the car,
  # verifies SLAM publishes /map. Heavy (~30 s locally, up to ~3 min on
  # a slow CI runner — the fixture polls for topic advertisement instead
  # of fixed sleeps, so wall-time tracks how fast the box is). Opt-out
  # via -DBUILD_TESTING=OFF or `--ctest-args -E test_slam_e2e`.
  ament_add_pytest_test(test_slam_e2e test/test_slam_e2e.py
    TIMEOUT 300
  )
endif()

ament_package()
