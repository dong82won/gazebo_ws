#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path


def patch_portrait_dae_files(base_path: str):
    root_dir = Path(base_path).resolve()
    if not root_dir.exists():
        print(f"[ERROR] 경로를 찾을 수 없습니다: {root_dir}")
        return

    # ../../../../photos/PortraitX_YY.jpg 패턴 매칭
    pattern = re.compile(
        r"<init_from>(\.\./)+photos/(Portrait[A-Z]_\d{2})\.jpg</init_from>",
        re.IGNORECASE,
    )

    dae_files = list(root_dir.rglob("*.DAE")) + list(root_dir.rglob("*.dae"))
    patched_count = 0

    for dae_file in dae_files:
        try:
            with open(dae_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if "photos/Portrait" in content:
                # ../materials/textures/aws_PortraitX_YY.png 로 자동 교체
                new_content = pattern.sub(
                    r"<init_from>../materials/textures/aws_\2.png</init_from>",
                    content,
                )

                if new_content != content:
                    with open(dae_file, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"[PATCH SUCCESS] {dae_file.relative_to(root_dir)}")
                    patched_count += 1
        except Exception as e:
            print(f"[ERROR] 파일 처리 실패 ({dae_file.name}): {e}")

    print(f"\n총 {patched_count}개의 DAE 파일이 성공적으로 패치되었습니다.")


if __name__ == "__main__":
    # 소스(src) 및 빌드(install) 디렉터리 경로 설정
    default_src_path = os.path.expanduser(
        "~/PNS/100_Development/110_ROS2JAZZY/gazebo_ws/src/aws_robomaker_hospital_world/models"
    )
    target_path = sys.argv[1] if len(sys.argv) > 1 else default_src_path
    patch_portrait_dae_files(target_path)
