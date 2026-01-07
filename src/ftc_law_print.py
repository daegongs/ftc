import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import os
import re
from urllib.parse import urlparse
import random

# PDF 변환을 위한 라이브러리 (playwright 사용)
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    print("Warning: playwright가 설치되지 않았습니다.")
    print("py -m pip install playwright 명령으로 설치해주세요.")
    print("설치 후: playwright install chromium")

# --- Constants ---
INPUT_FILE = "ftc_law_data.xlsx"
OUTPUT_DIR = "pdf_output"
BASE_URL = "https://www.ftc.go.kr"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/109.0.1518.78",
]

def sanitize_filename(filename):
    """파일명에서 사용할 수 없는 문자 제거"""
    # Windows에서 사용할 수 없는 문자 제거
    invalid_chars = r'[<>:"/\\|?*]'
    filename = re.sub(invalid_chars, '_', filename)
    # 길이 제한 (Windows 파일명 최대 길이 고려)
    if len(filename) > 200:
        filename = filename[:200]
    return filename

def fetch_page_content(url, session=None):
    """웹페이지 내용을 가져옵니다."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://www.ftc.go.kr/"
    }
    
    try:
        if session:
            response = session.get(url, headers=headers, timeout=15)
        else:
            response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # 인코딩 처리
        if response.apparent_encoding and ('euc-kr' in response.apparent_encoding.lower() or 'cp949' in response.apparent_encoding.lower()):
            response.encoding = response.apparent_encoding
        else:
            response.encoding = 'utf-8'
        
        return response.text
    except Exception as e:
        print(f"  ERROR: 페이지 가져오기 실패 ({url}): {e}")
        return None

def save_page_as_pdf(url, output_path, playwright_context=None):
    """웹페이지를 PDF로 저장합니다 (playwright 사용)."""
    print(f"  처리 중: {url}")
    
    try:
        if not HAS_PLAYWRIGHT:
            print("  ERROR: playwright가 설치되지 않았습니다.")
            return False
        
        if playwright_context is None:
            print("  ERROR: playwright context가 제공되지 않았습니다.")
            return False
        
        # 페이지 열기
        page = playwright_context.new_page()
        
        # 페이지 로드 (타임아웃 30초)
        page.goto(url, wait_until='networkidle', timeout=30000)
        
        # PDF로 저장
        page.pdf(
            path=output_path,
            format='A4',
            print_background=True,
            margin={
                'top': '1cm',
                'right': '1cm',
                'bottom': '1cm',
                'left': '1cm'
            }
        )
        
        page.close()
        
        # 파일 크기 확인
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / 1024  # KB
            print(f"  [OK] PDF 저장 완료: {output_path} ({file_size:.1f} KB)")
            return True
        else:
            print(f"  [ERROR] PDF 파일이 생성되지 않았습니다.")
            return False
            
    except Exception as e:
        print(f"  ERROR: PDF 저장 실패: {e}")
        return False

def process_excel_to_pdf():
    """엑셀 파일을 읽어서 각 링크의 페이지를 PDF로 저장합니다."""
    
    # playwright 확인
    if not HAS_PLAYWRIGHT:
        print("\n[ERROR] playwright 라이브러리가 필요합니다.")
        print("다음 명령으로 설치해주세요:")
        print("  py -m pip install playwright")
        print("  playwright install chromium")
        return
    
    # 엑셀 파일 읽기
    print(f"엑셀 파일 읽는 중: {INPUT_FILE}")
    try:
        df = pd.read_excel(INPUT_FILE)
    except FileNotFoundError:
        print(f"[ERROR] 파일을 찾을 수 없습니다: {INPUT_FILE}")
        return
    except Exception as e:
        print(f"[ERROR] 엑셀 파일 읽기 실패: {e}")
        return
    
    # 컬럼 확인
    if '팝업페이지링크' not in df.columns:
        print("[ERROR] '팝업페이지링크' 컬럼을 찾을 수 없습니다.")
        print(f"사용 가능한 컬럼: {list(df.columns)}")
        return
    
    # 출력 디렉토리 생성
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"출력 디렉토리 생성: {OUTPUT_DIR}")
    
    # playwright 브라우저 시작
    print("\n브라우저를 시작하는 중...")
    playwright_instance = sync_playwright().start()
    browser = playwright_instance.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent=random.choice(USER_AGENTS)
    )
    
    # 각 행 처리
    total = len(df)
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    print(f"\n총 {total}개의 링크를 처리합니다.\n")
    
    try:
        for idx, row in df.iterrows():
            link = row.get('팝업페이지링크', '')
            law_name = row.get('법령명', f'법령_{idx+1}')
            
            # 유효하지 않은 링크 스킵
            if pd.isna(link) or link == '' or link.startswith('N/A') or link.startswith('javascript:'):
                print(f"[{idx+1}/{total}] 스킵: {law_name} (유효하지 않은 링크)")
                skip_count += 1
                continue
            
            # 파일명 생성
            safe_law_name = sanitize_filename(str(law_name))
            pdf_filename = f"{idx+1:03d}_{safe_law_name}.pdf"
            pdf_path = os.path.join(OUTPUT_DIR, pdf_filename)
            
            # 이미 파일이 있으면 스킵 (선택사항)
            if os.path.exists(pdf_path):
                print(f"[{idx+1}/{total}] 스킵: {law_name} (이미 존재)")
                skip_count += 1
                continue
            
            print(f"[{idx+1}/{total}] {law_name}")
            
            # PDF 저장
            if save_page_as_pdf(link, pdf_path, context):
                success_count += 1
            else:
                fail_count += 1
            
            # 서버 부하 방지를 위한 대기
            time.sleep(1)
    
    finally:
        # 브라우저 종료
        print("\n브라우저를 종료하는 중...")
        context.close()
        browser.close()
        playwright_instance.stop()
    
    # 결과 요약
    print("\n" + "="*50)
    print("처리 완료!")
    print(f"  성공: {success_count}개")
    print(f"  실패: {fail_count}개")
    print(f"  스킵: {skip_count}개")
    print(f"  총계: {total}개")
    print(f"\nPDF 파일 저장 위치: {os.path.abspath(OUTPUT_DIR)}")
    print("="*50)

if __name__ == "__main__":
    print("="*50)
    print("FTC 법령 팝업 페이지 PDF 변환 프로그램")
    print("="*50)
    
    process_excel_to_pdf()

