# FTC Law Navigator (공정위 법령 내비게이터)

공정거래위원회(FTC) 소관 법령 정보를 웹 기반으로 검색, 수집하고 상세 정보를 PDF 및 엑셀로 자동 변환하는 지능형 업무 자동화 대시보드입니다.

## 🌟 주요 기능

### 1. 실시간 법령 스크래핑 대시보드 (`app.py`)
- **웹 인터페이스**: Flask 기반의 직관적인 UI를 통해 법령 수집 과정을 실시간으로 모니터링합니다.
- **카테고리별 수집**: 공정거래법, 하도급법, 가맹사업법 등 14개 주요 카테고리별 선택적 수집 기능을 제공합니다.
- **시행/개정 정보 자동 추출**: 국가법령정보센터 Open API를 통해 각 법령의 최신 시행일, 개정 유형, 개정 정보 등을 자동으로 조회합니다.

### 2. 시행/개정 정보 수집 (Open API 연동)
- **국가법령정보센터 API**: `law.go.kr` Open API를 통해 실시간 법령 정보 조회
- **공공데이터포털 API**: `data.go.kr` 법제처 국가법령정보 공유서비스 연동 지원
- **자동 엔드포인트 전환**: API 키 형식에 따라 적절한 서버를 자동 선택

### 3. 스마트 PDF 저장 및 관리
- **지능형 콘텐츠 추출**: Playwright를 이용해 국가법령정보센터(`law.go.kr`)의 iframe 구조 내에서 실제 본문 내용만을 정확히 추출합니다.
- **커스텀 스타일링**: PDF 생성 시 제목, 시행 정보 등을 포함한 가독성 높은 레이아웃을 적용합니다.
- **메타데이터 설정**: 생성된 PDF 파일의 메타데이터에 상세 법령 명칭을 자동으로 기록합니다.
- **ZIP 일괄 다운로드**: 수집된 모든 법령 PDF를 ZIP 파일로 일괄 다운로드할 수 있습니다.

### 4. 고품질 엑셀 리포트 생성
- **스타일링 적용**: `openpyxl`을 활용하여 헤더 배경색, 테두리, 열 너비 최적화 등 업무용으로 즉시 사용 가능한 깔끔한 엑셀 파일을 생성합니다.
- **데이터 구조화**: 법령명, 구분, 상세명, 담당부서, 개정유형, 시행일 등을 체계적으로 정리합니다.

## 🛠 기술 스택

- **Backend**: Python 3.x, Flask (Web Server)
- **API Integration**: 국가법령정보센터 Open API, 공공데이터포털 API
- **Scraping/Automation**: BeautifulSoup4, Requests, Playwright
- **Data Processing**: Pandas, OpenPyxl
- **PDF Generation**: Playwright
- **Containerization**: Docker, Docker Compose
- **UI Components**: HTML5, Vanilla CSS, JavaScript (실시간 상태 업데이트)

## 🚀 시작하기

### 방법 1: Docker 실행 (권장)

```bash
# 프로젝트 디렉토리로 이동
cd ftc

# Docker 컨테이너 빌드 및 실행
docker-compose up -d

# 브라우저에서 접속
# http://localhost:8082
```

### 방법 2: 로컬 실행

```bash
# 필요한 패키지 설치
pip install -r requirements.txt
playwright install chromium

# 웹 어플리케이션 실행
python src/app.py

# 브라우저에서 http://localhost:5000 접속
```

## ⚙️ API 설정 (.env 파일)

프로젝트 루트에 `.env` 파일을 생성하고 API 키를 설정합니다:

```env
# 국가법령정보센터 Open API (open.law.go.kr)
# OC 값 = 등록한 이메일의 @ 앞부분 (예: user@example.com → user)
LAW_API_KEY_PERSONAL=your_email_id

# 공공데이터포털 API (data.go.kr) - 선택사항
# 법제처 국가법령정보 공유서비스 ServiceKey
LAW_API_KEY_CORPORATE=your_service_key
```

### API 키 발급 방법

#### 방법 1: 국가법령정보센터 (open.law.go.kr)
1. [https://open.law.go.kr](https://open.law.go.kr) 접속 및 회원가입
2. 로그인 후 **"Open API 신청"** 메뉴 클릭
3. 사용할 API 서비스 선택 후 신청
4. 승인 완료 후, **등록한 이메일의 @ 앞부분**을 `.env` 파일에 입력
5. 문의: 법제처 공동활용 유지보수팀 (02-2109-6446)

#### 방법 2: 공공데이터포털 (data.go.kr)
1. [https://data.go.kr](https://data.go.kr) 접속 및 회원가입
2. **"법제처 국가법령정보 공유서비스"** 검색 후 활용 신청
3. 발급받은 ServiceKey를 `.env` 파일의 `LAW_API_KEY_CORPORATE`에 입력

## 📖 사용 방법

1. **[데이터 수집]** 버튼: FTC 웹사이트에서 법령 목록을 스크래핑합니다.
2. **[시행/개정 정보 수집]** 버튼: Open API를 통해 각 법령의 시행일, 개정유형 등을 조회합니다.
3. **[엑셀파일 저장]** 버튼: 수집된 데이터를 스타일링된 엑셀 파일로 다운로드합니다.
4. **[법령 PDF 저장]** 버튼: 각 법령의 상세 내용을 PDF로 저장하고 ZIP으로 다운로드합니다.

## 📂 프로젝트 구조

```
ftc/
├── src/                   # 주요 소스코드 및 템플릿
│   ├── app.py             # Flask 웹 서버 및 메인 비즈니스 로직
│   ├── scraper.py         # FTC 사이트 법령 목록 스크래핑 엔진
│   ├── law_scraper.py     # 상세 법령 및 시행일 추출 엔진
│   ├── extract_links.py   # 링크 추출 유틸리티
│   └── templates/
│       └── index.html     # 대시보드 웹 페이지
├── output/                # 생성된 엑셀/PDF 결과물 저장소
├── .env                   # API 키 설정 파일 (git에서 제외됨)
├── requirements.txt       # Python 패키지 의존성
├── Dockerfile.ftc         # Docker 이미지 빌드 설정
├── docker-compose.yml     # Docker Compose 설정
└── README.md              # 프로젝트 문서
```

## 🔧 문제 해결

### API 오류 (키 확인) 메시지가 표시되는 경우

1. `.env` 파일의 API 키가 올바르게 설정되었는지 확인
2. 국가법령정보센터의 경우, **이메일 ID**(@ 앞부분)만 입력해야 함
3. API 신청이 승인 완료되었는지 확인
4. Docker 사용 시 컨테이너 재시작: `docker-compose restart ftc`

### 연결 오류가 발생하는 경우

1. 인터넷 연결 상태 확인
2. 방화벽에서 `law.go.kr`, `data.go.kr` 접근이 차단되지 않았는지 확인
3. Docker 네트워크 설정 확인

## 📝 참고 사항

- **Headless 브라우저**: 서버 환경 및 로컬 환경 모두에서 작동하도록 Headless 모드를 기본으로 지원합니다.
- **팝업 처리**: 국가법령정보센터의 복잡한 팝업 및 iframe 구조를 자동으로 해석하도록 설계되었습니다.
- **캐시 방지**: 브라우저 캐시로 인한 데이터 미갱신 문제를 방지하기 위해 No-Cache 헤더가 적용되어 있습니다.

## 📄 라이선스

이 프로젝트는 내부 업무 자동화 목적으로 개발되었습니다.
