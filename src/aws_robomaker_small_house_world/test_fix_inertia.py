#!/usr/bin/env python3
"""AWS RoboMaker Model Inertia Matrix Validator & Fixer for Gazebo Harmonic.

Enforces physical validity required by the DART physics engine:
1. Mass > 0
2. Strictly positive principal moments (Ixx, Iyy, Izz > 0)
3. Triangular inequalities (Ixx + Iyy >= Izz, etc.)
4. Positive-definite inertia matrix via Sylvester's criterion
"""

import logging
import shutil
import sys
import xml.etree.ElementTree as ET
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger("InertiaFixer")


@dataclass(slots=True)
class InertiaTensor:
    """3x3 대칭 관성 텐서 표현 및 물리적 유효성 검증 클래스."""

    ixx: float
    iyy: float
    izz: float
    ixy: float = 0.0
    ixz: float = 0.0
    iyz: float = 0.0

    def is_positive_definite(self) -> bool:
        """실베스터 판정법(Sylvester's criterion)을 이용한 양의 정부호성 검증."""
        # 1차 주소행렬식
        if self.ixx <= 0:
            return False

        # 2차 주소행렬식: ixx * iyy - ixy^2
        d2 = (self.ixx * self.iyy) - (self.ixy**2)
        if d2 <= 0:
            return False

        # 3차 행렬식 (전체 디터미넌트)
        d3 = (
            self.ixx * (self.iyy * self.izz - self.iyz**2)
            - self.ixy * (self.ixy * self.izz - self.ixz * self.iyz)
            + self.ixz * (self.ixy * self.iyz - self.iyy * self.ixz)
        )
        return d3 > 0

    def satisfies_triangle_inequality(self) -> bool:
        """주관성 모멘트의 삼각 부등식 검증 (A + B >= C)."""
        return (
            (self.ixx + self.iyy >= self.izz)
            and (self.iyy + self.izz >= self.ixx)
            and (self.izz + self.ixx >= self.iyy)
        )

    def is_physically_valid(self) -> bool:
        """DART 물리 엔진 기준 종합 적합성 검사."""
        if self.ixx <= 0 or self.iyy <= 0 or self.izz <= 0:
            return False
        if not self.satisfies_triangle_inequality():
            return False
        return self.is_positive_definite()

    @classmethod
    def create_safe_diagonal(cls, mass: float) -> "InertiaTensor":
        """물리적으로 안정적인 기본 관성 텐서 생성 (반경 0.2m, 높이 0.5m 원통 근사)."""
        safe_ixx = round(mass * 0.1, 4)
        safe_iyy = round(mass * 0.1, 4)
        safe_izz = round(mass * 0.05, 4)
        return cls(
            ixx=safe_ixx,
            iyy=safe_iyy,
            izz=safe_izz,
            ixy=0.0,
            ixz=0.0,
            iyz=0.0,
        )


class SdfModelPatcher:
    """SDF 파일 내의 <link> 관성 속성을 분석하고 자동 보정하는 패처."""

    DEFAULT_MASS = 1.0

    def __init__(self, dry_run: bool = False, create_backup: bool = True) -> None:
        self.dry_run = dry_run
        self.create_backup = create_backup

    def process_file(self, sdf_path: Path) -> bool:
        """단일 model.sdf 파일의 관성 데이터를 검증하고 필요한 경우 갱신합니다."""
        try:
            tree = ET.parse(sdf_path)
            root = tree.getroot()
        except (ET.ParseError, OSError) as exc:
            logger.error("XML 파싱 실패: %s (원인: %s)", sdf_path, exc)
            return False

        file_modified = False

        for link in root.iter("link"):
            link_name = link.attrib.get("name", "unnamed_link")
            inertial = link.find("inertial")
            if inertial is None:
                continue

            # 1. 질량 검증 및 보정
            mass_elem = inertial.find("mass")
            if mass_elem is None:
                mass_elem = ET.SubElement(inertial, "mass")
                mass_elem.text = str(self.DEFAULT_MASS)
                mass = self.DEFAULT_MASS
                file_modified = True
            else:
                try:
                    mass = float(mass_elem.text) if mass_elem.text else 0.0
                except ValueError:
                    mass = 0.0

                if mass <= 0:
                    mass = self.DEFAULT_MASS
                    mass_elem.text = str(self.DEFAULT_MASS)
                    file_modified = True

            # 2. 관성 텐서 검증 및 보정
            inertia_elem = inertial.find("inertia")
            if inertia_elem is None:
                inertia_elem = ET.SubElement(inertial, "inertia")
                safe_tensor = InertiaTensor.create_safe_diagonal(mass)
                self._write_tensor(inertia_elem, safe_tensor)
                file_modified = True
            else:
                tensor = self._read_tensor(inertia_elem)
                if not tensor.is_physically_valid():
                    safe_tensor = InertiaTensor.create_safe_diagonal(mass)
                    self._write_tensor(inertia_elem, safe_tensor)
                    file_modified = True
                    logger.warning(
                        "부적격 관성 텐서 교정: [%s -> 링크 '%s']",
                        sdf_path.parent.name,
                        link_name,
                    )

        if file_modified and not self.dry_run:
            if self.create_backup:
                backup_path = sdf_path.with_suffix(".sdf.orig")
                if not backup_path.exists():
                    shutil.copy2(sdf_path, backup_path)

            ET.indent(tree, space="  ")
            tree.write(sdf_path, encoding="utf-8", xml_declaration=True)
            logger.info("보정 완료 파일 저장: %s", sdf_path)

        return file_modified

    @staticmethod
    def _read_tensor(inertia_elem: ET.Element) -> InertiaTensor:
        """XML 엘리먼트로부터 6개 관성 텐서 성분을 읽어옵니다."""
        vals: dict[str, float] = {}
        for tag in ["ixx", "iyy", "izz", "ixy", "ixz", "iyz"]:
            elem = inertia_elem.find(tag)
            try:
                vals[tag] = float(elem.text) if elem is not None and elem.text else 0.0
            except ValueError:
                vals[tag] = 0.0
        return InertiaTensor(**vals)

    @staticmethod
    def _write_tensor(inertia_elem: ET.Element, tensor: InertiaTensor) -> None:
        """수정된 텐서 값을 XML 자식 노드에 작성합니다."""
        mapping = {
            "ixx": tensor.ixx,
            "iyy": tensor.iyy,
            "izz": tensor.izz,
            "ixy": tensor.ixy,
            "ixz": tensor.ixz,
            "iyz": tensor.iyz,
        }
        for tag, val in mapping.items():
            elem = inertia_elem.find(tag)
            if elem is None:
                elem = ET.SubElement(inertia_elem, tag)
            elem.text = str(val)

    def scan_directory(self, target_dir: Path) -> tuple[int, int]:
        """디렉토리를 재귀 탐색하여 모든 model.sdf를 보정합니다."""
        sdf_files = list(target_dir.rglob("model.sdf"))
        repaired = 0
        for sdf in sdf_files:
            if self.process_file(sdf):
                repaired += 1
        return len(sdf_files), repaired


def parse_arguments(args: list[str]) -> Namespace:
    """명령줄 인수 파서 구성."""
    parser = ArgumentParser(
        description="Gazebo Harmonic 호환 SDF 모델 관성 행렬 일괄 보정 도구"
    )
    parser.add_argument(
        "models_dir",
        type=Path,
        nargs="?",
        default=Path.home()
        / "PNS/100_Development/110_ROS2JAZZY/gazebo_ws/src/aws_robomaker_small_house_world/models",
        help="검사 및 보정할 models 디렉토리 경로",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 파일을 수정하지 않고 검증 결과만 출력",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="수정 전 .orig 백업 파일 생성을 비활성화",
    )
    return parser.parse_args(args)


def main() -> None:
    """엔트리포인트 실행 함수."""
    parsed_args = parse_arguments(sys.argv[1:])
    target_path = parsed_args.models_dir.resolve()

    if not target_path.exists():
        logger.error("대상 경로가 존재하지 않습니다: %s", target_path)
        sys.exit(1)

    logger.info("모델 스캔 시작 대상: %s", target_path)
    patcher = SdfModelPatcher(
        dry_run=parsed_args.dry_run,
        create_backup=not parsed_args.no_backup,
    )
    total_found, total_fixed = patcher.scan_directory(target_path)
    logger.info(
        "처리 완료: 총 %d개 파일 중 %d개 파일 보정됨.", total_found, total_fixed
    )


if __name__ == "__main__":
    main()
