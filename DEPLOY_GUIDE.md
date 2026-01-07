# FTC 프로젝트 폐쇄망 배포 가이드 (Windows -> Gateway -> Dev Server)

본 가이드는 인터넷 통신이 불가한 리눅스 개발 서버(`Navix 9.6 / RHEL 9`) 환경에서 브라우저 자동화 프로젝트(`ftc`)를 안정적으로 배포하기 위한 최종 절차를 정리한 문서입니다.

## 0. 환경 정보
- **로컬 컴퓨터**: Windows 11
- **게이트웨이**: `dgw01` (계정: `daegong`)
- **개발 서버**: `dev-laai-ncl` (계정: `irteam`)
- **서버 OS / Python**: Navix 9.6 (RHEL 9 기반) / Python 3.9.21
- **설치 경로**: `/home1/irteam/projects/ftc`

---

## 1단계: 로컬(Windows) 사전 준비

### 1-1. `requirements.txt` 최적화
- 리눅스 바이너리가 없는 `mcp-playwright`는 주석 처리합니다.
- 서버 버전(3.9)에 필요한 의존성(`importlib-metadata`, `exceptiongroup` 등)을 고려한 구성을 유지합니다.

### 1-2. 오프라인 설치 패키지 수집
로컬 터미널(PowerShell)에서 아래 명령어를 실행하여 리눅스용 패키지를 다운로드합니다.
```powershell
# packages 폴더가 없다면 생성
mkdir -Force packages

# Python 3.9 및 RHEL 9 환경용 패키지 수집
pip download -d ./packages -r requirements.txt `
    "importlib-metadata>=3.6.0" "zipp" "exceptiongroup" "typing-extensions" "h11" "sniffio" `
    --platform manylinux2014_x86_64 `
    --platform manylinux1_x86_64 `
    --platform manylinux_2_28_x86_64 `
    --only-binary=:all: `
    --python-version 3.9
```

### 1-3. 리눅스용 Chromium 드라이버 준비
서버에서 직접 다운로드가 불가하므로 리눅스용 바이너리를 미리 준비합니다.
1. [Linux용 Chromium](https://playwright.azureedge.net/builds/chromium/1148/chromium-linux.zip) 다운로드
2. 프로젝트 내 `browser_bin` 폴더를 생성하고 압축 해제
   - 경로: `ftc/browser_bin/chrome-linux/chrome` 존재 확인

---

## 2단계: 프로젝트 압축 및 전송

### 2-1. 단일 압축 파일 생성
다중 파일 전송 제한을 우회하기 위해 하나의 파일로 합칩니다.
```powershell - 폴더 전체 압축하는 경우
# PowerShell에서 수행 
Compress-Archive -Path "C:\Users\USER\projects\ftc\*" -DestinationPath "C:\Users\USER\projects\ftc_deploy_ssl_fix.zip" -Force
```
```powershell - 변경된 파일만 압축하는 경우
# src 폴더 내부의 app.py와 scraper.py만 골라서 압축
Compress-Archive -Path "C:\Users\USER\projects\ftc\src\app.py", "C:\Users\USER\projects\ftc\src\scraper.py" -DestinationPath "C:\Users\USER\projects\ftc\update.zip" -Force
```

### 2-2. 2단계 전송 (Gateway 경유)
```powershell
# 1. 로컬 -> 게이트웨이 (daegong 계정)
scp "C:\Users\USER\projects\ftc_deploy_ssl_fix.zip" daegong@dgw01:~/

# 2. 게이트웨이 접속 및 개발서버 전송
ssh daegong@dgw01
# (게이트웨이 터미널에서 실행)
scp ~/ftc_deploy_ssl_fix.zip irteam@dev-laai-ncl:/home1/irteam/projects/
```

---

## 3단계: 개발 서버 설치 및 설정

### 3-1. 기존 환경 정리 (권한 오류 해결)
파일 락(Lock)이나 권한 문제를 방지하기 위해 기존 폴더를 완전히 정리합니다.
```bash
# 개발 서버 접속
ssh irteam@dev-laai-ncl
cd /home1/irteam/projects/

# 기존 앱 및 브라우저 프로세스 종료
pkill -f "python3 src/app.py"
pkill -f "chrome"

# 기존 폴더 권한 강제 부여 후 삭제
chmod -R 777 ftc
rm -rf ftc
```

### 3-2. 압축 해제 및 패키지 설치
```bash
# 압축 해제
unzip ftc_deploy_ssl_fix.zip -d ftc
cd ftc

# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 오프라인 모드로 패키지 일괄 설치
pip install --no-index --find-links=./packages -r requirements.txt
```

### 3-3. 브라우저 실행 권한 부여
```bash
chmod -R 755 ./browser_bin/
chmod +x ./browser_bin/chrome-linux/chrome
```

---

## 4단계: 실행 및 모니터링

### 4-1. 애플리케이션 가동
실행 시 외부 접속을 허용(`host='0.0.0.0'`)하도록 설정된 `app.py`를 가동합니다.
```bash
# 백그라운드 실행 (로그 저장)
nohup python3 src/app.py > output.log 2>&1 &
```

### 4-2. 상태 확인
- **프로세스**: `ps -ef | grep python`
- **로그 확인**: `tail -f output.log`
- **웹 접속**: `http://dev-laai-ncl:5000` or 'http://10.177.143.126:5000'

---

## ⚠️ 주요 트러블슈팅 요약
1. **ImportError (importlib-metadata 등)**: Python 3.10 미만에서는 별도 의존성이 필요함. 반드시 `pip download` 시 명시적으로 포함할 것.
2. **Permission Denied (unzip)**: 브라우저 프로세스가 살아있으면 덮어쓰기가 안 됨. `pkill` 후 삭제하고 다시 진행할 것.
3. **OS Library Error**: 만약 실행 시 `.so` 파일 부족 에러 발생 시 서버 관리자에게 `dnf install` 요청 필요.
