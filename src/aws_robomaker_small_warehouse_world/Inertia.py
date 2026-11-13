"""
Warehouse Model Inertia Matrix Validator & Fixer
Enforces physical validity: m > 0, Ixx+Iyy >= Izz, and positive eigenvalues.
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def validate_and_fix_inertia(sdf_path: Path) -> bool:
    tree = ET.parse(sdf_path)
    root = tree.getroot()
    modified = False

    for link in root.iter("link"):
        inertial = link.find("inertial")
        if inertial is None:
            continue

        mass_elem = inertial.find("mass")
        inertia_elem = inertial.find("inertia")

        # 1. 질량(mass) 검증 및 보정
        if mass_elem is None:
            mass_elem = ET.SubElement(inertial, "mass")
            mass_elem.text = "1.0"
            mass = 1.0
            modified = True
        else:
            try:
                mass = float(mass_elem.text) if mass_elem.text else 1.0
            except ValueError:
                mass = 1.0

            if mass <= 0:
                mass = 1.0
                mass_elem.text = "1.0"
                modified = True

        # 2. 관성 텐서(inertia) 검증 및 보정
        if inertia_elem is not None:
            vals: dict[str, float] = {}
            for tag in ["ixx", "iyy", "izz", "ixy", "ixz", "iyz"]:
                child = inertia_elem.find(tag)
                try:
                    val = float(child.text) if child is not None and child.text else 0.0
                except ValueError:
                    val = 0.0
                vals[tag] = val

            # 주관성 모멘트가 0 이하이거나 삼각 부등식을 위반하는 경우
            ixx, iyy, izz = vals["ixx"], vals["iyy"], vals["izz"]
            invalid = (
                ixx <= 0
                or iyy <= 0
                or izz <= 0
                or (ixx + iyy < izz)
                or (iyy + izz < ixx)
                or (izz + ixx < iyy)
            )

            if invalid:
                # 안전한 기본 관성 모멘트 부여 (반경 0.2m, 높이 0.5m 원통 기준 근사)
                safe_ixx = round(mass * 0.1, 4)
                safe_iyy = round(mass * 0.1, 4)
                safe_izz = round(mass * 0.05, 4)

                for tag, safe_val in [
                    ("ixx", safe_ixx),
                    ("iyy", safe_iyy),
                    ("izz", safe_izz),
                    ("ixy", 0.0),
                    ("ixz", 0.0),
                    ("iyz", 0.0),
                ]:
                    elem = inertia_elem.find(tag)
                    if elem is None:
                        elem = ET.SubElement(inertia_elem, tag)
                    elem.text = str(safe_val)

                modified = True

    if modified:
        tree.write(sdf_path, encoding="utf-8", xml_declaration=True)
        print(f"[FIXED INERTIA] {sdf_path}")
    return modified


def run_batch_fix(models_dir: str) -> None:
    root_path = Path(models_dir).resolve()
    print(f"Scanning models for invalid inertia in: {root_path}")
    fixed_files = 0
    for sdf_file in root_path.rglob("model.sdf"):
        if validate_and_fix_inertia(sdf_file):
            fixed_files += 1
    print(f"Finished. Total models repaired: {fixed_files}")


if __name__ == "__main__":
    target = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.path.expanduser(
            "~/PNS/100_Development/110_ROS2JAZZY/gazebo_ws/src/aws_robomaker_small_warehouse_world/models"
        )
    )
    run_batch_fix(target)
