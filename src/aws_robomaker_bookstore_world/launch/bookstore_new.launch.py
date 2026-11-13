"""
Universal Production-Grade Gazebo Harmonic World Launch Template for ROS 2 Jazzy.

Design Principles:
1. Zero Hardcoded Paths: Fully dynamic resolution of workspace assets via AMENT_PREFIX_PATH.
2. Cross-Package Asset Discovery: Exposes all sourced ROS 2 share directories to Gazebo Harmonic.
3. Robust Argument Parsing: Ensures the '-r' flag is strictly preserved for active physics stepping.
4. Process Isolation: Decouples server (-s) and GUI (-g) to eliminate OGRE2 rendering context crashes.
5. Strict Type Hinting: Compliant with Modern Python 3.12+ engineering standards.

"""

import os

from ament_index_python.packages import (
    PackageNotFoundError,
    get_package_share_directory,
)
from launch import LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable,
    DeclareLaunchArgument,
    IncludeLaunchDescription,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    # -------------------------------------------------------------------------
    # 1. 시뮬레이션 타깃 패키지 및 코어 패키지 디렉터리 동적 해석
    # -------------------------------------------------------------------------
    target_world_package: str = "aws_robomaker_bookstore_world"

    try:
        pkg_world = get_package_share_directory(target_world_package)
    except PackageNotFoundError:
        pkg_world = ""

    pkg_ros_gz_sim = get_package_share_directory("ros_gz_sim")

    # -------------------------------------------------------------------------
    # 2. 런치 설정 인자 (Launch Arguments)
    # -------------------------------------------------------------------------
    declared_arguments: list[DeclareLaunchArgument] = [
        DeclareLaunchArgument(
            name="world",
            default_value="bookstore.world",
            description="Name of the world SDF file inside the package worlds directory",
        ),
        DeclareLaunchArgument(
            name="headless",
            default_value="false",
            description="Run Gazebo Sim in server-only headless mode (-s)",
        ),
        DeclareLaunchArgument(
            name="use_sim_time",
            default_value="true",
            description="Synchronize ROS nodes with Gazebo simulation clock (/clock)",
        ),
    ]

    world_arg = LaunchConfiguration("world")
    headless_arg = LaunchConfiguration("headless")
    use_sim_time_arg = LaunchConfiguration("use_sim_time")

    # -------------------------------------------------------------------------
    # 3. 제로-하드코딩: AMENT_PREFIX_PATH 기반 동적 에셋 파이프라인 구성
    # -------------------------------------------------------------------------
    # 런타임에 체이닝 소싱된 모든 워크스페이스의 prefix 경로 추출
    ament_prefix_path = os.environ.get("AMENT_PREFIX_PATH", "")
    discovered_shares: list[str] = [
        os.path.join(prefix, "share")
        for prefix in ament_prefix_path.split(":")
        if prefix and os.path.isdir(os.path.join(prefix, "share"))
    ]

    # 대상 월드 패키지 내부 models 디렉터리 우선순위 부여
    resource_paths: list[str] = []
    if pkg_world:
        models_dir = os.path.join(pkg_world, "models")
        if os.path.isdir(models_dir):
            resource_paths.append(models_dir)
        resource_paths.append(pkg_world)

    # 중복을 제거하면서 순서를 보존하여 전체 share 경로 병합
    for share in discovered_shares:
        if share not in resource_paths:
            resource_paths.append(share)

    combined_resource_str = ":".join(resource_paths)

    # Gazebo Sim 및 ROS package:// 해석용 환경 변수 주입
    set_gz_resource_path = AppendEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH",
        value=combined_resource_str,
    )

    set_ros_package_path = AppendEnvironmentVariable(
        name="ROS_PACKAGE_PATH",
        value=combined_resource_str,
    )

    # -------------------------------------------------------------------------
    # 4. 월드 전체 경로 및 Gazebo CLI 파라미터 구성
    # -------------------------------------------------------------------------
    world_full_path = PathJoinSubstitution(
        [FindPackageShare(target_world_package), "worlds", world_arg]
    )

    # Process 1: Gazebo Server Process (-r -s: 즉시 물리 연산 실행, 헤드리스)
    # 리스트 치환자 [world_full_path, " -r -s"] 결합으로 -r 유실 방지
    gz_server = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={
            "gz_args": [world_full_path, " -r -s"],
        }.items(),
    )

    # Process 2: Gazebo GUI Process (-g: 독립 윈도우 렌더링 컨텍스트)
    # OGRE2 싱글톤 씬 충돌을 근본 차단하기 위해 Server와 완전 분리 실행
    gz_gui = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={"gz_args": "-g"}.items(),
        condition=UnlessCondition(headless_arg),
    )

    # -------------------------------------------------------------------------
    # 5. 글로벌 시뮬레이션 시계 (/clock) 브리지 노드
    # -------------------------------------------------------------------------
    clock_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="global_clock_bridge",
        output="screen",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
        condition=IfCondition(use_sim_time_arg),
    )

    return LaunchDescription(
        declared_arguments
        + [
            set_gz_resource_path,
            set_ros_package_path,
            gz_server,
            gz_gui,
            clock_bridge,
        ]
    )
