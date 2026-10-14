"""파일 분류 도우미 (웹 버전, Streamlit Cloud용)

파일을 올리면 종류·수정한 달별 폴더로 나눈 zip을 만들어 내려받게 한다.
올린 파일은 서버에 저장하지 않고 메모리에서만 처리한다.
로컬 실행:  streamlit run streamlit_app.py
"""
import io
import zipfile
from collections import Counter
from datetime import date, datetime
from pathlib import PurePosixPath

import pandas as pd
import streamlit as st

from sort_files import DEFAULT_CATEGORIES, OTHER, category_of

MODE_LABELS = {
    "종류별 + 월별 (예: 문서/2026-10)": "ext_month",
    "종류별만 (예: 문서)": "ext",
    "월별만 (예: 2026-10)": "month",
}
SKIP_NAMES = {"Thumbs.db", "desktop.ini", ".DS_Store"}


def zip_entry_name(info):
    """윈도우 탐색기로 만든 zip의 한글 이름(cp949)이 깨지지 않게 고친다."""
    if info.flag_bits & 0x800:  # UTF-8로 저장된 이름
        return info.filename
    try:
        return info.filename.encode("cp437").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def collect_files(uploads):
    """올린 파일들 → [(파일 이름, 내용 bytes, 수정한 달)]. zip은 풀어서 안의 파일을 쓴다."""
    today = date.today().strftime("%Y-%m")
    files, notes = [], []
    for up in uploads:
        data = up.getvalue()
        if up.name.lower().endswith(".zip") and len(uploads) == 1:
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    for info in zf.infolist():
                        name = PurePosixPath(zip_entry_name(info).replace("\\", "/")).name
                        if info.is_dir() or not name or name in SKIP_NAMES or "__MACOSX" in info.filename:
                            continue
                        month = "{:04d}-{:02d}".format(*info.date_time[:2])
                        files.append((name, zf.read(info), month))
                notes.append("압축 파일 안의 파일을 꺼내, 원래 수정한 날짜 기준으로 나눴습니다.")
                continue
            except zipfile.BadZipFile:
                notes.append(f"'{up.name}'은 열 수 없는 압축 파일이라 그대로 '압축' 종류로 분류합니다.")
        files.append((up.name, data, today))
    return files, notes


def target_folder(name, month, mode):
    cat = category_of(PurePosixPath(name), DEFAULT_CATEGORIES)
    return cat, {"ext_month": f"{cat}/{month}", "ext": cat, "month": month}[mode]


def unique_path(path, used):
    """같은 폴더에 같은 이름이 있으면 '이름 (2).확장자'처럼 번호를 붙인다."""
    if path not in used:
        return path
    p = PurePosixPath(path)
    i = 2
    while (candidate := str(p.with_name(f"{p.stem} ({i}){p.suffix}"))) in used:
        i += 1
    return candidate


def make_plan(files, mode):
    plan, used = [], set()
    for name, data, month in files:
        cat, folder = target_folder(name, month, mode)
        path = unique_path(f"{folder}/{name}", used)
        used.add(path)
        plan.append({"name": name, "data": data, "category": cat, "month": month, "folder": folder, "path": path})
    return plan


def build_zip(plan):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in plan:
            zf.writestr(item["path"], item["data"])
    return buf.getvalue()


def count_table(plan):
    counts = Counter(item["folder"] for item in plan)
    table = pd.DataFrame(sorted(counts.items()), columns=["폴더", "파일 수"])
    table.loc[len(table)] = ["합계", int(table["파일 수"].sum())]
    return table


st.set_page_config(page_title="파일 분류 도우미", page_icon="🗂️")
st.title("🗂️ 파일 분류 도우미")
st.write(
    "파일을 올리면 **종류(문서·엑셀·이미지 등)**와 **수정한 달**에 따라 폴더로 나눠서, "
    "**zip 파일 하나로 내려받을 수 있게** 만들어 줍니다.  \n"
    "올린 파일은 서버에 저장되지 않고, 이 화면을 닫으면 사라집니다."
)

# ① 파일 올리기
st.subheader("① 정리할 파일 올리기")
uploads = st.file_uploader(
    "파일을 끌어다 놓거나 'Browse files'를 눌러 고르세요 (여러 개 가능)",
    accept_multiple_files=True,
)
st.caption(
    "💡 **수정한 날짜를 살리고 싶다면** 폴더를 통째로 압축(zip)해서 그 zip 파일 **하나만** 올리세요.  \n"
    "파일을 하나씩 올리면 웹 특성상 수정 날짜를 알 수 없어서 **오늘 날짜(올린 달)**로 나눕니다."
)
if not uploads:
    st.info("먼저 파일을 올려 주세요.")
    st.stop()

files, notes = collect_files(uploads)
for n in notes:
    st.caption("ℹ " + n)
if not files:
    st.warning("올린 파일에서 정리할 파일을 찾지 못했습니다.")
    st.stop()
st.caption(f"정리할 파일: {len(files)}개")

# ② 나누는 방법
st.subheader("② 나누는 방법")
mode = MODE_LABELS[st.radio("폴더를 어떻게 나눌까요?", list(MODE_LABELS))]
with st.expander("파일 종류는 이렇게 구분합니다"):
    st.table(pd.DataFrame(
        [{"종류": k, "파일 확장자": ", ".join(sorted(e.lstrip(".") for e in v))} for k, v in DEFAULT_CATEGORIES.items()]
        + [{"종류": OTHER, "파일 확장자": "위에 없는 나머지 모두"}]
    ).set_index("종류"))

plan = make_plan(files, mode)
renamed = sum(1 for item in plan if item["path"] != f"{item['folder']}/{item['name']}")

# ③ 미리보기 / 실행
st.subheader("③ 확인하고 내려받기")
col1, col2 = st.columns(2)
preview = col1.button("👀 미리보기", width="stretch", help="어느 폴더로 갈지만 보여줍니다.")
run = col2.button("✅ 분류 실행", type="primary", width="stretch", help="나눈 결과를 zip 파일로 만듭니다.")

if preview:
    st.info("아래 내용이 괜찮으면 **분류 실행**을 누르세요.")
    st.dataframe(
        pd.DataFrame([
            {"파일 이름": i["name"], "종류": i["category"], "수정한 달": i["month"], "들어갈 폴더": i["folder"]}
            for i in plan
        ]),
        hide_index=True,
        width="stretch",
    )
    st.write("폴더별 예상 개수")
    st.dataframe(count_table(plan), hide_index=True)

if run:
    with st.spinner("zip 파일을 만드는 중입니다…"):
        zip_bytes = build_zip(plan)
    st.success(f"완료! 파일 {len(plan)}개를 정리했습니다. 아래 버튼으로 내려받으세요.")
    st.dataframe(count_table(plan), hide_index=True)
    if renamed:
        st.write(f"• 같은 폴더에 이름이 같은 파일 {renamed}개는 뒤에 (2), (3)… 번호를 붙였습니다.")
    st.download_button(
        "⬇️ 분류 결과 내려받기 (zip)",
        data=zip_bytes,
        file_name=f"분류결과_{datetime.now():%Y%m%d_%H%M}.zip",
        mime="application/zip",
        type="primary",
        width="stretch",
    )
