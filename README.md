# FTC Law Navigator (공정위 법령 내비게이터)

공정거래위원회(FTC) 소관 법령 정보를 웹 기반으로 검색, 수집하고 상세 정보를 PDF 및 엑셀로 자동 변환하는 지능형 업무 자동화 대시보드입니다.

## 🌟 주요 기능

### 1. 실시간 법령 스크래핑 대시보드 (`app.py`)
- **웹 인터페이스**: Flask 기반의 직관적인 UI를 통해 법령 수집 과정을 실시간으로 모니터링합니다.
- **카테고리별 수집**: 공정거래법, 하도급법, 가맹사업법 등 14개 주요 카테고리별 선택적 수집 기능을 제공합니다.
- **시행/개정 정보 자동 추출**: Selenium과 Playwright를 활용하여 각 법령의 최신 시행일, 개정 유형, 개정 정보 등을 자동으로 파싱합니다.

### 2. 스마트 PDF 저장 및 관리
- **지능형 콘텐츠 추출**: Playwright를 이용해 국가법령정보센터(`law.go.kr`)의 iframe 구조 내에서 실제 본문 내용만을 정확히 추출합니다.
- **커스텀 스타일링**: PDF 생성 시 제목, 시행 정보 등을 포함한 가독성 높은 레이아웃을 적용합니다.
- **메타데이터 설정**: 생성된 PDF 파일의 메타데이터에 상세 법령 명칭을 자동으로 기록합니다.
- **로컬 저장 기능**: `tkinter` 폴더 선택기를 통해 사용자가 원하는 위치에 직접 PDF를 저장하거나 ZIP으로 일괄 다운로드할 수 있습니다.

### 3. 고품질 엑셀 리포트 생성
- **스타일링 적용**: `openpyxl`을 활용하여 헤더 배경색, 테두리, 열 너비 최적화 등 업무용으로 즉시 사용 가능한 깔끔한 엑셀 파일을 생성합니다.
- **데이터 구조화**: 법령명, 구분, 상세명, 담당부서, 개정유형, 시행일 등을 체계적으로 정리합니다.

### 4. 업무 배포 자동화 (`distribute_by_manager.py`)
- **담당자별 배포**: 대규모 기업집단의 임원지분현황 데이터를 담당자-법인 매핑 정보에 따라 자동으로 시트를 분리하여 배포용 파일을 생성합니다.

## 🛠 기술 스택

- **Backend**: Python 3.x, Flask (Web Server)
- **Scraping/Automation**: BeautifulSoup4, Selenium, Playwright
- **Data Processing**: Pandas, OpenPyxl
- **PDF Generation**: Playwright, PyPDF (Metadata)
- **UI Components**: HTML5, Vanilla CSS, JS (Progress Bar, 실시간 상태 업데이트)

## 🚀 시작하기

### 1. 환경 설정
필요한 패키지를 설치합니다:
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 웹 어플리케이션 실행
```bash
python app.py
```
브라우저에서 `http://localhost:5000`에 접속하여 사용합니다.

### 3. 주요 모듈 단독 실행 (필요시)
- **법령 추출**: `python scraper.py`
- **PDF 변환**: `python ftc_law_print.py`
- **담당자별 파일 배포**: `python distribute_by_manager.py`

## 📂 프로젝트 구조
- `app.py`: 웹 서버 및 메인 비즈니스 로직 (스크래핑, PDF 생성 통합 제어)
- `scraper.py`: FTC 사이트 기본 목록 수집 엔진
- `templates/`: 대시보드 웹 페이지 템플릿
- `output/`: 생성된 엑셀 및 PDF 결과물 임시 저장소
- `smer/`: 업무 배포용 원본 데이터 저장소

## 📝 참고 사항
- **Headless 브라우저**: 서버 환경 및 로컬 환경 모두에서 작동하도록 Headless 모드를 기본으로 지원합니다.
- **팝업 처리**: 국가법령정보센터의 복잡한 팝업 및 iframe 구조를 자동으로 해석하도록 설계되었습니다.
- **저장 경로**: 로컬에서 실행 시 PDF 저장 위치를 직접 선택할 수 있는 편의 기능을 제공합니다.

