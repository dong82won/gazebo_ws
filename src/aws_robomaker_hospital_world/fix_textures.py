#!/usr/bin/env python3
"""
Industrial AMR/Cobot Digital Twin Asset Fixer
Fixes broken relative texture paths in Gazebo Sim (Harmonic) DAE files.
"""

import os
import re
import sys
from pathlib import Path


def generate_minimal_jpeg(output_path: Path, color_rgb=(180, 180, 180)) -> None:
    """외부 의존성 없이 유효한 최소 단위 단색 JPEG 파일을 바이너리로 생성합니다."""
    # 1x1 단색 더미 이미지용 표준 JFIF 바이너리 헤더 및 데이터 블록
    r, g, b = color_rgb
    # YCbCr 변환 (단순화된 근사치)
    y = int(0.299 * r + 0.587 * g + 0.114 * b)
    cb = int(128 - 0.168736 * r - 0.331264 * g + 0.5 * b)
    cr = int(128 + 0.5 * r - 0.418688 * g - 0.081312 * b)

    # 최소 구조 JPEG 바이너리 스트림 (Baseline DCT)
    jpeg_bytes = bytes(
        [
            0xFF,
            0xD8,  # SOI
            0xFF,
            0xE0,
            0x00,
            0x10,
            0x4A,
            0x46,
            0x49,
            0x46,
            0x00,
            0x01,
            0x01,
            0x00,
            0x00,
            0x01,
            0x00,
            0x01,
            0x00,
            0x00,  # APP0
            0xFF,
            0xDB,
            0x00,
            0x43,
            0x00,  # DQT
        ]
        + [0x10] * 64
        + [  # 양자화 테이블
            0xFF,
            0xC0,
            0x00,
            0x0B,
            0x08,
            0x00,
            0x01,
            0x00,
            0x01,
            0x01,
            0x01,
            0x11,
            0x00,  # SOF0 (1x1 Grayscale/Y)
            0xFF,
            0xC4,
            0x00,
            0x1F,
            0x00,  # DHT (DC)
            0x00,
            0x01,
            0x05,
            0x01,
            0x01,
            0x01,
            0x01,
            0x01,
            0x01,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x01,
            0x02,
            0x03,
            0x04,
            0x05,
            0x06,
            0x07,
            0x08,
            0x09,
            0x0A,
            0x0B,
            0xFF,
            0xDA,
            0x00,
            0x08,
            0x01,
            0x01,
            0x00,
            0x00,
            0x3F,
            0x00,  # SOS
            0x5B,
            0x20,  # 스캔 데이터 (압축 블록)
            0xFF,
            0xD9,  # EOI
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(jpeg_bytes)


def patch_dae_file(dae_path: Path, models_root: Path) -> int:
    """DAE 내부의 잘못된 텍스처 참조 경로를 탐색하고 로컬 참조로 정정합니다."""
    with open(dae_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # <init_from>...Portrait*.jpg</init_from> 또는 photos 관련 경로 매칭
    pattern = re.compile(
        r"<init_from>(?:file://)?(.*?[/\\])?([^/\\]+\.(?:jpg|png|jpeg))</init_from>",
        re.IGNORECASE,
    )

    matches = pattern.findall(content)
    if not matches:
        return 0

    fixed_count = 0
    meshes_dir = dae_path.parent

    for _, filename in matches:
        target_texture = meshes_dir / filename

        # 텍스처 파일이 meshes/ 내에 없는 경우 처리
        if not target_texture.exists():
            # 1. 패키지 내 materials/textures 탐색
            found_path = None
            for p in models_root.rglob(filename):
                if p.is_file():
                    found_path = p
                    break

            if found_path:
                # 발견된 원본 텍스처를 meshes 폴더로 복사
                with open(found_path, "rb") as src, open(target_texture, "wb") as dst:
                    dst.write(src.read())
                print(f"  [COPIED] {found_path.name} -> {meshes_dir}")
            else:
                # 텍스처 파일이 완전히 누락된 경우 정규 단색 더미 이미지 자동 생성
                generate_minimal_jpeg(target_texture)
                print(f"  [GENERATED] Dummy Texture: {target_texture}")

        fixed_count += 1

    # DAE 파일 내용 수정: 모든 외부 경로를 파일명 단독(동일 폴더) 참조로 강제 변경
    new_content = pattern.sub(r"<init_from>\2</init_from>", content)

    if new_content != content:
        with open(dae_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"[PATCHED DAE] {dae_path.name}")

    return fixed_count


def run_fixer(target_dir: str):
    root_path = Path(target_dir).resolve()
    if not root_path.exists():
        print(f"[ERROR] Target path does not exist: {root_path}")
        sys.exit(1)

    print("=== Scanning Hospital World Assets for Texture Path Anomalies ===")
    print(f"Target Directory: {root_path}\n")

    dae_files = list(root_path.rglob("*.dae"))
    total_fixed = 0

    for dae in dae_files:
        fixed = patch_dae_file(dae, root_path)
        total_fixed += fixed

    print(f"\n[COMPLETE] Total texture references resolved: {total_fixed}")


if __name__ == "__main__":
    # 사용자 워크스페이스의 패키지 소스 모델 디렉터리 기본값
    default_path = os.path.expanduser(
        "~/PNS/100_Development/110_ROS2JAZZY/gazebo_ws/src/aws_robomaker_hospital_world/models"
    )

    target_directory = sys.argv[1] if len(sys.argv) > 1 else default_path
    run_fixer(target_directory)
