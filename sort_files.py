"""폴더의 파일을 확장자별 → 수정 연월(YYYY-MM)별로 sorted 폴더에 복사한다.

사용법
  python sort_files.py [원본폴더] [--rule 분류=확장자,확장자 ...] [--mode 방식] [--dry-run]

  원본폴더  생략하면 이 스크립트 옆의 mixed 폴더
  --rule    분류 규칙. 여러 번 줄 수 있고, 주면 기본 규칙 대신 이것만 쓴다
            예) --rule 문서=docx,hwp,pdf --rule 이미지=jpg,png
  --mode    ext_month(기본): 분류/YYYY-MM,  ext: 분류,  month: YYYY-MM
  --dry-run 미리보기만 하고 파일은 건드리지 않는다

결과는 원본폴더 옆의 sorted 폴더에 만들고, 원본은 복사만 한다(지우지 않음).
실행할 때마다 언제, 무엇을 했는지 원본폴더 옆의 output/실행로그.txt 에 덧붙여 기록한다.
app.py(Streamlit 화면)도 이 파일의 함수를 그대로 쓴다.
"""
import argparse
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# exe(PyInstaller)로 실행하면 __file__이 임시 폴더를 가리키므로 exe가 있는 폴더를 기준으로 한다
BASE = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent

DEFAULT_CATEGORIES = {
    "문서": {".docx", ".hwp", ".hwpx", ".pdf", ".txt", ".pptx"},
    "엑셀": {".xlsx", ".xls", ".csv"},
    "이미지": {".jpg", ".jpeg", ".png", ".gif"},
    "압축": {".zip", ".7z"},
}
OTHER = "기타"
MODES = ("ext_month", "ext", "month")


def parse_rule(text):
    """'문서=docx,.hwp' → ('문서', {'.docx', '.hwp'})"""
    name, _, exts = text.partition("=")
    if not name.strip() or not exts.strip():
        raise argparse.ArgumentTypeError(f"규칙 형식이 잘못됐습니다: {text} (예: 문서=docx,pdf)")
    return name.strip(), {"." + e.strip().lstrip(".").lower() for e in exts.split(",") if e.strip()}


def category_of(path, categories):
    ext = path.suffix.lower()  # DSC0001.JPG 같은 대문자 확장자도 처리
    for name, exts in categories.items():
        if ext in exts:
            return name
    return OTHER


def paths_for(src):
    """원본 폴더 → (결과 폴더, 실행로그 파일)"""
    return src.parent / "sorted", src.parent / "output" / "실행로그.txt"


def make_plan(src, categories=DEFAULT_CATEGORIES, mode="ext_month"):
    """파일마다 어디로 복사할지 정한다. 파일은 건드리지 않는다."""
    dst, _ = paths_for(src)
    plan = []
    for f in sorted(src.iterdir()):
        if not f.is_file():
            continue
        cat = category_of(f, categories)
        month = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m")
        folder = {"ext_month": dst / cat / month, "ext": dst / cat, "month": dst / month}[mode]
        plan.append({"source": f, "category": cat, "month": month, "target": folder / f.name})
    return plan


def find_stale(plan, dst):
    """sorted 안의 다른 위치에 남은, 이름이 같은 예전 복사본 목록"""
    previous = {}
    if dst.exists():
        for p in dst.rglob("*"):
            if p.is_file():
                previous.setdefault(p.name, []).append(p)
    stale = []
    for item in plan:
        stale += [old for old in previous.get(item["source"].name, []) if old != item["target"]]
    return stale


def execute(src, plan, remove_stale=True, mode="ext_month", categories=DEFAULT_CATEGORIES):
    """계획대로 복사하고 로그를 남긴다. 폴더별 개수(Counter)와 집계 dict를 돌려준다."""
    dst, log_txt = paths_for(src)
    log = [
        "=" * 60,
        f"실행 시각: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"원본: {src}",
        f"결과: {dst}",
        f"방식: {mode}",
        "규칙: " + " / ".join(f"{k}={','.join(sorted(v))}" for k, v in categories.items()) + f" / 나머지={OTHER}",
    ]
    stale = find_stale(plan, dst) if remove_stale else []
    stats = {"ok": 0, "fail": 0, "overwritten": 0, "removed": 0}
    for old in stale:
        try:
            old.unlink()
            log.append(f"  예전 복사본 삭제: {old.relative_to(dst).as_posix()}")
            stats["removed"] += 1
        except OSError as e:
            log.append(f"  예전 복사본 삭제 실패: {old.relative_to(dst).as_posix()} ({e})")

    counts = Counter()
    for item in plan:
        f, target = item["source"], item["target"]
        rel = target.relative_to(dst).as_posix()
        try:
            existed = target.exists()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)  # copy2: 수정 날짜도 그대로 유지
            log.append(f"  성공: {f.name} → {rel}" + (" (기존 파일 덮어씀)" if existed else ""))
            counts[target.parent.relative_to(dst).as_posix()] += 1
            stats["ok"] += 1
            stats["overwritten"] += existed
        except OSError as e:
            log.append(f"  실패: {f.name} → {rel} ({e})")
            stats["fail"] += 1

    log.append(
        f"결과: 성공 {stats['ok']}개 (덮어씀 {stats['overwritten']}개), 실패 {stats['fail']}개, "
        f"예전 복사본 삭제 {stats['removed']}개 (원본은 그대로)"
    )
    log += [f"  {folder}: {n}개" for folder, n in sorted(counts.items())]
    write_log(log_txt, log)
    return counts, stats


def write_log(log_txt, lines):
    """실행 기록을 output/실행로그.txt 맨 뒤에 덧붙인다."""
    log_txt.parent.mkdir(exist_ok=True)
    with open(log_txt, "a", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n\n")


def print_table(counts):
    table = [f"{'폴더':<16}{'파일 수':>6}", "-" * 24]
    table += [f"{folder:<16}{n:>6}" for folder, n in sorted(counts.items())]
    table += ["-" * 24, f"{'합계':<16}{sum(counts.values()):>6}"]
    print("\n".join(table))


def main():
    ap = argparse.ArgumentParser(description="확장자·수정 연월별 파일 분류(복사)")
    ap.add_argument("src", nargs="?", default=str(BASE / "mixed"), help="분류할 원본 폴더")
    ap.add_argument("--rule", action="append", type=parse_rule, help="분류=확장자,확장자")
    ap.add_argument("--mode", choices=MODES, default="ext_month", help="폴더 나누는 방식")
    ap.add_argument("--dry-run", action="store_true", help="미리보기만 함")
    args = ap.parse_args()

    src = Path(args.src).resolve()
    if not src.is_dir():
        sys.exit(f"원본 폴더가 없습니다: {src}")
    dst, log_txt = paths_for(src)
    categories = dict(args.rule) if args.rule else DEFAULT_CATEGORIES
    plan = make_plan(src, categories, args.mode)

    if args.dry_run:
        stale = find_stale(plan, dst)
        for old in stale:
            print(f"삭제 예정(예전 복사본): {old.relative_to(dst).as_posix()}")
        print_table(Counter(item["target"].parent.relative_to(dst).as_posix() for item in plan))
        print(f"\n[미리보기] 파일은 바뀌지 않았습니다. 실행 시 지워질 예전 복사본: {len(stale)}개")
        return

    counts, stats = execute(src, plan, True, args.mode, categories)
    print_table(counts)
    if stats["removed"]:
        print(f"다른 폴더에 남아 있던 예전 복사본 {stats['removed']}개를 지웠습니다.")
    print(f"\n로그 저장: {log_txt}")
    if stats["fail"]:
        print(f"실패 {stats['fail']}개 — 자세한 내용은 실행로그.txt를 확인하세요.")


if __name__ == "__main__":
    main()
