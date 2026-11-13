import os

from ament_index_python.packages import get_package_share_directory
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
    # 1. 대상 패키지 및 ros_gz_sim 경로 정의
    target_world_package = "aws_robomaker_hospital_world"

    pkg_world = get_package_share_directory(target_world_package)
    pkg_ros_gz_sim = get_package_share_directory("ros_gz_sim")

    # 2. Launch 인자 선언
    world_arg = DeclareLaunchArgument(
        "world",
        default_value="hospital.world",
        description="Name of the world file located inside the package's worlds directory",
    )

    headless_arg = DeclareLaunchArgument(
        "headless",
        default_value="false",
        description="Run Gazebo Sim without GUI (-s flag)",
    )

    # 3. Gazebo Sim(Harmonic) 환경 변수 설정 (GZ_SIM_RESOURCE_PATH)
    models_path = os.path.join(pkg_world, "models")
    worlds_path = os.path.join(pkg_world, "worlds")

    # 런타임에 소싱된 모든 워크스페이스의 share 경로를 추가하여 의존 패키지 간 모델 참조 허용
    ament_prefix = os.environ.get("AMENT_PREFIX_PATH", "")
    additional_shares = ":".join(
        [os.path.join(p, "share") for p in ament_prefix.split(":") if p]
    )

    set_gz_resource_path = AppendEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH",
        value=f"{models_path}:{worlds_path}:{pkg_world}:{additional_shares}",
    )

    world_full_path = PathJoinSubstitution(
        [FindPackageShare(target_world_package), "worlds", LaunchConfiguration("world")]
    )

    # 4. Gazebo Sim 서버 실행 (GUI 모드)
    gz_sim_gui = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={"gz_args": ["-r ", world_full_path]}.items(),
        condition=UnlessCondition(LaunchConfiguration("headless")),
    )

    # 5. Gazebo Sim 서버 실행 (Headless 모드: CI/CD 및 HIL 검증용)
    gz_sim_headless = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={"gz_args": ["-r -s ", world_full_path]}.items(),
        condition=IfCondition(LaunchConfiguration("headless")),
    )

    # 6. 전역 시뮬레이션 클럭(/clock) 브리지 노드 실행
    clock_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="global_clock_bridge",
        output="screen",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
    )

    return LaunchDescription(
        [
            world_arg,
            headless_arg,
            set_gz_resource_path,
            gz_sim_gui,
            gz_sim_headless,
            clock_bridge,
        ]
    )
