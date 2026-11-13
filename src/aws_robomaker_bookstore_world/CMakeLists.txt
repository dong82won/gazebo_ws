cmake_minimum_required(VERSION 3.5)
project(aws_robomaker_bookstore_world)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)

# 정적 리소스 설치
install(DIRECTORY
  launch
  models
  worlds
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
