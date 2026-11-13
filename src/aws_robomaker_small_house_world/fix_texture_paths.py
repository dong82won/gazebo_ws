#!/usr/bin/env python3
"""Texture Relative Path Validator & Fixer for AWS Small House World Models.

Handles both lower-case (*.dae) and upper-case (*.DAE) COLLADA files.
Replaces invalid 4-level parent traversals (../../../../photos/) with
3-level parent traversals (../../../photos/).
"""

import logging
import shutil
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger("TextureFixer")


class DaeTexturePatcher:
    """COLLADA 메쉬 파일의 텍스처 상대 경로 패턴을 교정하는 클래스."""

    TARGET_PATTERN = "../../../../photos/"
    REPLACEMENT_PATTERN = "../../../photos/"

    def __init__(self, dry_run: bool = False, create_backup: bool = True) -> None:
        self.dry_run = dry_run
        self.create_backup = create_backup

    def process_file(self, dae_path: Path) -> bool:
        """단일 DAE 파일의 텍스처 경로를 교정합니다."""
        try:
            content = dae_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            logger.error("파일 읽기 실패: %s (원인: %s)", dae_path, exc)
            return False

        if self.TARGET_PATTERN not in content:
            return False

        count = content.count(self.TARGET_PATTERN)
        updated_content = content.replace(self.TARGET_PATTERN, self.REPLACEMENT_PATTERN)

        logger.info("패턴 감지 (%d건): %s", count, dae_path.name)

        if not self.dry_run:
            if self.create_backup:
                backup_path = dae_path.with_suffix(f"{dae_path.suffix}.orig")
                if not backup_path.exists():
                    shutil.copy2(dae_path, backup_path)

            dae_path.write_text(updated_content, encoding="utf-8")
            logger.info("파일 수정 완료: %s", dae_path.name)

        return True

    def scan_and_fix(self, target_dir: Path) -> tuple[int, int]:
        """대소문자 무관하게 모든 COLLADA 메쉬 파일을 검색하여 보정합니다."""
        # Linux ext4 대소문자 구분 문제 해결: 소문자 및 대문자 확장자 모두 수집
        dae_files = [
            p
            for p in target_dir.rglob("*")
            if p.is_file() and p.suffix.lower() == ".dae"
        ]

        if not dae_files:
            logger.warning("검사할 DAE 메쉬 파일이 없습니다: %s", target_dir)
            return 0, 0

        logger.info("총 %d개의 COLLADA 메쉬 파일 검색됨.", len(dae_files))
        modified_count = 0
        for file_path in dae_files:
            if self.process_file(file_path):
                modified_count += 1

        return len(dae_files), modified_count


def parse_arguments(args: list[str]) -> Namespace:
    """명령줄 인수 파서 구성."""
    parser = ArgumentParser(
        description="AWS Small House 모델 메쉬의 깨진 텍스처 경로 자동 보정 도구"
    )
    parser.add_argument(
        "models_dir",
        type=Path,
        nargs="?",
        default=Path(__file__).resolve().parent / "models",
        help="검사 대상 models 디렉토리 (기본값: 스크립트 동일 위치의 models/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="파일을 수정하지 않고 대상 파일만 출력",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="수정 전 원본 백업 파일(.orig) 생성 비활성화",
    )
    return parser.parse_args(args)


def main() -> None:
    """메인 실행 함수."""
    parsed_args = parse_arguments(sys.argv[1:])
    target_path = parsed_args.models_dir.resolve()

    if not target_path.exists():
        logger.error("대상 디렉토리가 존재하지 않습니다: %s", target_path)
        sys.exit(1)

    logger.info("메쉬 텍스처 스캔 시작 디렉토리: %s", target_path)
    patcher = DaeTexturePatcher(
        dry_run=parsed_args.dry_run,
        create_backup=not parsed_args.no_backup,
    )
    total_found, total_fixed = patcher.scan_and_fix(target_path)
    logger.info(
        "스캔 완료: 총 %d개 DAE 파일 중 %d개 파일 수정됨.",
        total_found,
        total_fixed,
    )


if __name__ == "__main__":
    main()
