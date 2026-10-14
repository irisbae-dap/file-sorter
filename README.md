# 파일 분류 도우미 (file-sorter)

파일을 올리면 **종류(문서·엑셀·이미지·압축·기타)**와 **수정한 달**에 따라 폴더로 나눠 zip으로 내려받게 해 주는 웹 앱입니다.

## 쓰는 법
1. 파일 여러 개를 올리거나, 폴더를 압축한 zip 하나를 올립니다.
   - zip으로 올리면 원래 수정 날짜를 기준으로 나눕니다.
   - 파일을 하나씩 올리면 올린 날짜(이번 달) 기준으로 나눕니다.
2. 나누는 방법을 고릅니다: 종류별 + 월별 / 종류별만 / 월별만
3. **미리보기**로 확인한 뒤 **분류 실행** → **분류 결과 내려받기**

올린 파일은 서버에 저장되지 않습니다.

## 파일 종류 구분
| 종류 | 확장자 |
|---|---|
| 문서 | docx, hwp, hwpx, pdf, txt, pptx |
| 엑셀 | xlsx, xls, csv |
| 이미지 | jpg, jpeg, png, gif |
| 압축 | zip, 7z |
| 기타 | 그 밖의 모든 파일 |

규칙은 `sort_files.py`의 `DEFAULT_CATEGORIES`에서 바꿀 수 있습니다.

## 내 PC에서 실행
```
pip install -r requirements.txt
streamlit run streamlit_app.py
```
