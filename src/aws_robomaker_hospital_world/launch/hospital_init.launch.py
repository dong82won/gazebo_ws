#!/usr/bin/env python3

import os
from pathlib import Path

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
    target_world_package: str = "aws_robomaker_hospital_world"
    pkg_ros_gz_sim = get_package_share_directory("ros_gz_sim")

    try:
        pkg_world = get_package_share_directory(target_world_package)
    except PackageNotFoundError:
        pkg_world = ""

    # 1. 런치 인자 정의
    declared_arguments: list[DeclareLaunchArgument] = [
        DeclareLaunchArgument(
            name="world",
            default_value="hospital.world",
            description="Name of the world SDF file inside package worlds directory",
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
    # 2. 제로-하드코딩 스마트 에셋 리졸버 (Smart Asset Discovery Pipeline)
    # -------------------------------------------------------------------------
    discovered_resource_paths: set[str] = set()

    # (1) sim_asset_ws 전용 에셋 저장소 탐색
    sim_asset_root = Path("/home/won/PNS/100_Development/110_ROS2JAZZY/sim_asset_ws")
    if sim_asset_root.is_dir():
        discovered_resource_paths.add(str(sim_asset_root))
        worlds_path = sim_asset_root / "worlds"
        models_path = sim_asset_root / "models"

        if worlds_path.is_dir():
            discovered_resource_paths.add(str(worlds_path))
        if models_path.is_dir():
            discovered_resource_paths.add(str(models_path))
            # 1단계 하위 카테고리 폴더 추가
            for sub_dir in models_path.iterdir():
                if sub_dir.is_dir():
                    discovered_resource_paths.add(str(sub_dir))

    # (2) AMENT_PREFIX_PATH에 로드된 모든 워크스페이스의 share 및 models 자동 수집
    ament_prefix = os.environ.get("AMENT_PREFIX_PATH", "")
    for prefix in ament_prefix.split(":"):
        if not prefix:
            continue
        share_candidate = Path(prefix) / "share"
        if share_candidate.is_dir():
            discovered_resource_paths.add(str(share_candidate))
            # 각 패키지 share 하위의 models 디렉터리 수집
            for pkg_dir in share_candidate.iterdir():
                if pkg_dir.is_dir():
                    pkg_models = pkg_dir / "models"
                    if pkg_models.is_dir():
                        discovered_resource_paths.add(str(pkg_models))

    # (3) 현재 실행 대상 월드 패키지 경로 추가
    if pkg_world:
        discovered_resource_paths.add(pkg_world)
        local_models = Path(pkg_world) / "models"
        if local_models.is_dir():
            discovered_resource_paths.add(str(local_models))

    # 최종 콜론 구분자 문자열 조합 (공백 및 널 경로 배제)
    combined_resource_str = ":".join(sorted(list(discovered_resource_paths)))

    # 환경 변수 바인딩 (GZ_SIM_RESOURCE_PATH, SDF_PATH 동시 주입)
    set_gz_resource_path = AppendEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH",
        value=combined_resource_str,
    )
    set_sdf_path = AppendEnvironmentVariable(
        name="SDF_PATH",
        value=combined_resource_str,
    )
    set_ros_package_path = AppendEnvironmentVariable(
        name="ROS_PACKAGE_PATH",
        value=combined_resource_str,
    )

    # -------------------------------------------------------------------------
    # 3. Gazebo Harmonic 구동 (서버 및 GUI 프로세스 독립 실행)
    # -------------------------------------------------------------------------
    world_full_path = PathJoinSubstitution(
        [FindPackageShare(target_world_package), "worlds", world_arg]
    )

    # Gazebo Server Process (-r -s: 물리 엔진 즉시 연산)
    gz_server = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={
            "gz_args": [world_full_path, " -r -s"],
        }.items(),
    )

    # Gazebo GUI Process (-g: 독립 윈도우 렌더링 컨텍스트)
    gz_gui = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={"gz_args": "-g"}.items(),
        condition=UnlessCondition(headless_arg),
    )

    # -------------------------------------------------------------------------
    # 4. 글로벌 시뮬레이션 시계 동기화 노드
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
            set_sdf_path,
            set_ros_package_path,
            gz_server,
            gz_gui,
            clock_bridge,
        ]
    )
