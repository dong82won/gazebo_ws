#!/usr/bin/env python3
"""
Launch file for AWS Small House World simulation in Gazebo Harmonic.
Configures GZ_SIM_RESOURCE_PATH for model and texture discovery and bridges clock to ROS 2.
"""

import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable,
    DeclareLaunchArgument,
    IncludeLaunchDescription,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    """Generate launch description for Gazebo Harmonic small house world."""
    pkg_aws_house = get_package_share_directory("aws_robomaker_small_house_world")
    pkg_ros_gz_sim = get_package_share_directory("ros_gz_sim")

    models_path = os.path.join(pkg_aws_house, "models")
    default_world_path = str(Path(pkg_aws_house) / "worlds" / "small_house.world")

    # models 경로 및 photos가 포함된 패키지 루트를 탐색 경로에 함께 주입
    combined_resource_paths = f"{models_path}:{pkg_aws_house}"
    set_gz_resource_path = AppendEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH",
        value=combined_resource_paths,
    )

    world_arg = DeclareLaunchArgument(
        name="world",
        default_value=default_world_path,
        description="Full path to the SDF world file",
    )

    use_sim_time_arg = DeclareLaunchArgument(
        name="use_sim_time",
        default_value="true",
        description="Use simulation (Gazebo) clock if true",
    )

    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([pkg_ros_gz_sim, "launch", "gz_sim.launch.py"])
        ),
        launch_arguments={
            "gz_args": [LaunchConfiguration("world"), " -r"],
        }.items(),
    )

    clock_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="clock_bridge",
        output="screen",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
        condition=IfCondition(LaunchConfiguration("use_sim_time")),
    )

    return LaunchDescription(
        [
            set_gz_resource_path,
            world_arg,
            use_sim_time_arg,
            gz_sim,
            clock_bridge,
        ]
    )


if __name__ == "__main__":
    generate_launch_description()
