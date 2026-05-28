cmake_minimum_required(VERSION 3.8)
project(havoc_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_launches test/test_launches.py
    TIMEOUT 60
  )
endif()

ament_package()
