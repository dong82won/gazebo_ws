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
    target_pkg = "aws_robomaker_small_warehouse_world"
    pkg_share = get_package_share_directory(target_pkg)
    ros_gz_sim_share = get_package_share_directory("ros_gz_sim")

    # 1. 런치 인자 정의
    world_arg = DeclareLaunchArgument(
        "world",
        default_value="small_warehouse.world",
        description="World file path relative to the worlds directory",
    )
    headless_arg = DeclareLaunchArgument(
        "headless",
        default_value="false",
        description="Run Gazebo Sim without GUI (-s flag)",
    )

    # 2. 리소스 경로 환경 변수 (모델 및 월드 파싱)
    models_path = os.path.join(pkg_share, "models")
    worlds_path = os.path.join(pkg_share, "worlds")
    ament_prefix = os.environ.get("AMENT_PREFIX_PATH", "")
    additional_shares = ":".join(
        [os.path.join(p, "share") for p in ament_prefix.split(":") if p]
    )

    set_gz_resource_path = AppendEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH",
        value=f"{models_path}:{worlds_path}:{pkg_share}:{additional_shares}",
    )

    world_full_path = PathJoinSubstitution(
        [FindPackageShare(target_pkg), "worlds", LaunchConfiguration("world")]
    )

    # 3. Gazebo Sim 실행 (GUI / Headless 분기)
    gz_sim_gui = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim_share, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={"gz_args": ["-r ", world_full_path]}.items(),
        condition=UnlessCondition(LaunchConfiguration("headless")),
    )
    gz_sim_headless = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim_share, "launch", "gz_sim.launch.py")
        ),
        launch_arguments={"gz_args": ["-r -s ", world_full_path]}.items(),
        condition=IfCondition(LaunchConfiguration("headless")),
    )

    # 4. 시뮬레이션 클럭 동기화 브리지
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
