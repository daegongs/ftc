from flask import Flask, render_template, jsonify, send_file, request
import pandas as pd
import os
from datetime import datetime
import threading
from scraper import scrape_ftc_law_data

app = Flask(__name__)

# 전역 변수로 진행 상황 및 데이터 저장 (간이 세션/캐시 형태)
scraping_status = {
    "is_running": False,
    "progress": 0,
    "total": 0,
    "current_category": "",
    "data": [],
    "pdf_zip_path": None,  # PDF ZIP 파일 경로
    "target_dir": None    # 사용자가 선택한 저장 경로
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scrape/start', methods=['POST'])
def start_scrape():
    global scraping_status
    if scraping_status["is_running"]:
        return jsonify({"status": "error", "message": "이미 스크래핑이 진행 중입니다."})

    target_cd = request.json.get('target_cd', '1') # 'all' 또는 '1', '2' ...
    
    scraping_status["is_running"] = True
    scraping_status["progress"] = 0
    scraping_status["data"] = []
    
    # 별도 스레드에서 스크래핑 실행
    thread = threading.Thread(target=run_scraping_task, args=(target_cd,))
    thread.start()
    
    return jsonify({"status": "success", "message": "스크래핑을 시작합니다."})

def run_scraping_task(target_cd):
    global scraping_status
    all_dfs = []
    
    try:
        if target_cd == 'all':
            cds = [f"{i:02d}" for i in range(1, 15)]
        else:
            cds = [target_cd]
        
        # 진행률은 수집된 법령 건수 기준으로 표시
        scraping_status["total"] = 0  # 초기값 (수집하면서 갱신)
        scraping_status["progress"] = 0
        
        for idx, cd in enumerate(cds):
            cd_int = int(cd)
            scraping_status["current_category"] = f"카테고리 {cd} 수집 중... ({idx+1}/{len(cds)})"
            df = scrape_ftc_law_data(cd_int)
            if not df.empty:
                all_dfs.append(df)
                # 실시간으로 수집된 총 법령 건수 갱신
                total_laws = sum(len(d) for d in all_dfs)
                scraping_status["total"] = total_laws
                scraping_status["progress"] = total_laws
            
        if all_dfs:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            scraping_status["data"] = combined_df.to_dict('records')
            scraping_status["total"] = len(scraping_status["data"])
            scraping_status["progress"] = len(scraping_status["data"])
        
    except Exception as e:
        print(f"Scraping error: {e}")
    finally:
        scraping_status["is_running"] = False
        scraping_status["current_category"] = "완료"

@app.route('/api/scrape/info', methods=['POST'])
def scrape_info():
    """시행/개정 정보 수집 버튼 전용 API"""
    global scraping_status
    if not scraping_status["data"]:
        return jsonify({"status": "error", "message": "먼저 데이터 수집을 완료해주세요."})
    
    if scraping_status["is_running"]:
        return jsonify({"status": "error", "message": "이미 다른 작업이 진행 중입니다."})

    scraping_status["is_running"] = True
    scraping_status["progress"] = 0
    scraping_status["total"] = len(scraping_status["data"])
    
    thread = threading.Thread(target=run_info_update_task)
    thread.start()
    
    return jsonify({"status": "success", "message": "시행/개정 정보 수집을 시작합니다."})

def run_info_update_task():
    global scraping_status
    import time
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    # Chrome 옵션 설정 (Headless)
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        
        data_list = scraping_status["data"]
        for i, item in enumerate(data_list):
            current_info = item.get("시행/개정", "")
            if not current_info or current_info in ["N/A", "", "대기중", "정보없음"]:
                url = item.get("팝업페이지링크")
                if url and url.startswith("http"):
                    scraping_status["current_category"] = f"[{i+1}/{len(data_list)}] {item.get('법령명_상세')} 시행정보 수집 중..."
                    
                    try:
                        driver.get(url)
                        time.sleep(2) # 기본 로딩 대기
                        
                        extracted = ""
                        # 1. law.go.kr의 특수한 iframe 구조 처리
                        try:
                            # 대기 시간 증설 (5초 -> 10초)
                            wait = WebDriverWait(driver, 10)
                            
                            # lawService iframe이 로드될 때까지 대기
                            iframe = wait.until(EC.presence_of_element_located((By.ID, "lawService")))
                            driver.switch_to.frame(iframe)
                            
                            # 여러 셀렉터 후보 시도
                            # 법령(Laws): span.tx2
                            # 행정규칙/고시/예규(Administrative Rules): div.subtit1
                            selectors = ["span.tx2", "div.subtit1", "div.subtit2", "p.subtit1"]
                            for sel in selectors:
                                try:
                                    # 각 셀렉터별로 짧게 대기하며 확인
                                    target = WebDriverWait(driver, 2).until(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                                    )
                                    if target and '[시행' in target.text:
                                        extracted = target.text.strip()
                                        break
                                except:
                                    continue
                            
                            # 아직 못 찾았다면 iframe 내부에서 JS로 재검색
                            if not extracted:
                                extracted = driver.execute_script("""
                                    var elements = Array.from(document.querySelectorAll('*'));
                                    var target = elements.find(e => {
                                        var text = e.innerText || "";
                                        return text.includes('[시행') && text.includes(']') && e.children.length <= 1;
                                    });
                                    return target ? target.innerText : '';
                                """)
                            
                            driver.switch_to.default_content()
                        except Exception as e:
                            # 2. iframe이 없거나 실패한 경우 일반 페이지에서 검색
                            driver.switch_to.default_content()
                            try:
                                # 일반 페이지에서도 동일한 셀렉터들 시도
                                for sel in ["span.tx2", "div.subtit1", "div.subtit2"]:
                                    try:
                                        target = driver.find_element(By.CSS_SELECTOR, sel)
                                        if target and '[시행' in target.text:
                                            extracted = target.text.strip()
                                            break
                                    except: continue
                                
                                if not extracted:
                                    # 최후의 수단: '시행' 텍스트 포함 요소 검색 (JS 실행)
                                    extracted = driver.execute_script("""
                                        var el = Array.from(document.querySelectorAll('*')).find(e => 
                                            (e.innerText || "").includes('[시행') && (e.children.length === 0 || (e.children.length === 1 && e.firstElementChild.tagName === 'BR'))
                                        );
                                        return el ? el.innerText : '';
                                    """)
                            except:
                                pass
                        
                        if extracted:
                            # 데이터 파싱: [시행 2025. 1. 1.] [법률 제20101호, 2024. 1. 21., 일부개정]
                            import re
                            impl_date = ""
                            rev_type = ""
                            rev_info = ""
                            rev_date = ""
                            
                            # 시행일 추출
                            m1 = re.search(r'시행\s*([\d\.\s]+)', extracted)
                            if m1: impl_date = m1.group(1).strip()
                            
                            # 개정 상세 추출 (쉼표 분리 방식)
                            m2 = re.search(r'\]\s*\[([^\]]+)\]', extracted)
                            if m2:
                                parts = [p.strip() for p in m2.group(1).split(',')]
                                if len(parts) >= 1: rev_info = parts[0]
                                if len(parts) >= 2: rev_date = parts[1]
                                if len(parts) >= 3: rev_type = parts[2]

                            scraping_status["data"][i].update({
                                "시행/개정": extracted,
                                "시행일": impl_date or extracted,
                                "개정유형": rev_type,
                                "개정정보": rev_info,
                                "개정일": rev_date
                            })
                        else:
                            scraping_status["data"][i].update({
                                "시행/개정": "찾을 수 없음",
                                "시행일": "찾을 수 없음",
                                "개정유형": "-", "개정정보": "-", "개정일": "-"
                            })
                            
                    except Exception as e:
                        print(f"Error on row {i}: {e}")
                        scraping_status["data"][i].update({
                            "시행/개정": "오류", "시행일": "오류", "개정유형": "-", "개정정보": "-", "개정일": "-"
                        })
                        
                    time.sleep(0.5)
            scraping_status["progress"] = i + 1
            
    except Exception as e:
        print(f"Info update error: {e}")
    finally:
        if driver:
            driver.quit()
        scraping_status["is_running"] = False
        scraping_status["current_category"] = "정보 수집 완료 (법령 및 행정규칙/고시 정보 반영 완료)"

@app.route('/api/scrape/status')
def get_status():
    return jsonify({
        "is_running": scraping_status["is_running"],
        "progress": scraping_status["progress"],
        "total": scraping_status["total"],
        "current_category": scraping_status["current_category"],
        "data_count": len(scraping_status["data"])
    })

@app.route('/api/scrape/results')
def get_results():
    return jsonify(scraping_status["data"])

@app.route('/api/export/excel', methods=['POST'])
def export_excel():
    if not scraping_status["data"]:
        return jsonify({"status": "error", "message": "저장할 데이터가 없습니다."})
        
    df = pd.DataFrame(scraping_status["data"])
    
    # 컬럼 순서 고정 및 확장 (순서 변경: 개정유형, 시행일, 개정정보, 개정일)
    cols = ["법령명", "구분", "법령명_상세", "담당부서", "개정유형", "시행일", "개정정보", "개정일", "팝업페이지링크"]
    
    # 존재하지 않는 컬럼이 있을 경우 대비 (reindex로 안전하게 생성)
    df = df.reindex(columns=cols, fill_value="-")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"FTC_Laws_{timestamp}.xlsx"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    # 스타일링을 포함한 엑셀 저장
    try:
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='FTC_Laws')
            workbook = writer.book
            worksheet = writer.sheets['FTC_Laws']
            
            # 스타일 정의
            header_font = Font(name='맑은 고딕', bold=True, color='FFFFFF', size=11)
            header_fill = PatternFill(start_color='4F46E5', end_color='4F46E5', fill_type='solid')
            data_font = Font(name='맑은 고딕', size=10)
            alignment_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
            alignment_left = Alignment(horizontal='left', vertical='center', wrap_text=True)
            thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                               top=Side(style='thin'), bottom=Side(style='thin'))
            
            # 헤더 스타일 적용
            for cell in worksheet[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = alignment_center
                cell.border = thin_border
            
            # 데이터 스타일 및 너비 설정
            col_widths = {
                'A': 15, # 법령명
                'B': 12, # 구분
                'C': 35, # 법령명_상세
                'D': 15, # 담당부서
                'E': 12, # 개정유형
                'F': 15, # 시행일
                'G': 20, # 개정정보
                'H': 15, # 개정일
                'I': 20  # 링크
            }
            
            for col_letter, width in col_widths.items():
                worksheet.column_dimensions[col_letter].width = width
            
            # 전체 셀 테두리 및 정렬
            for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row):
                for cell in row:
                    cell.font = data_font
                    cell.border = thin_border
                    # 상세명과 주소는 왼쪽 정렬, 나머지는 중앙 정렬
                    if cell.column_letter in ['C', 'G', 'I']:
                        cell.alignment = alignment_left
                    else:
                        cell.alignment = alignment_center

    except Exception as e:
        print(f"Excel styling error: {e}")
        try:
            df.to_excel(filepath, index=False)
        except Exception as e2:
            return jsonify({"status": "error", "message": f"파일 저장 중 오류가 발생했습니다: {str(e2)}"})
    
    return jsonify({
        "status": "success", 
        "message": "파일이 성공적으로 생성되었습니다.",
        "filename": filename
    })

@app.route('/api/download/<filename>')
def download_file(filename):
    filepath = os.path.join(OUTPUT_DIR, filename)
    return send_file(filepath, as_attachment=True)

@app.route('/api/pdf/save', methods=['POST'])
def save_pdf():
    if not scraping_status["data"]:
        return jsonify({"status": "error", "message": "저장할 데이터가 없습니다."})
    
    if scraping_status["is_running"]:
        return jsonify({"status": "error", "message": "현재 다른 작업이 진행 중입니다."})

    # 폴더 선택 다이얼로그 띄우기 (로컬 실행 환경 가정)
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        target_dir = filedialog.askdirectory(title="PDF 파일들을 저장할 폴더를 선택하세요")
        root.destroy()
        
        if not target_dir:
            return jsonify({"status": "error", "message": "저장 위치가 선택되지 않았습니다."})
        
        # 선택된 경로가 존재하지 않으면 생성
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        scraping_status["target_dir"] = target_dir
    except Exception as e:
        print(f"Directory picker error: {e}")
        # GUI를 띄울 수 없는 환경인 경우 기본 output 폴더 사용
        scraping_status["target_dir"] = None

    # ZIP 경로 초기화
    scraping_status["pdf_zip_path"] = None
    scraping_status["is_running"] = True
    scraping_status["progress"] = 0
    scraping_status["total"] = len(scraping_status["data"])
    
    thread = threading.Thread(target=run_pdf_save_task, args=(scraping_status["target_dir"],))
    thread.start()
    
    target_msg = f"선택하신 폴더({os.path.basename(scraping_status['target_dir'])})" if scraping_status["target_dir"] else "기본 output 폴더"
    return jsonify({"status": "success", "message": f"{target_msg}에 PDF 저장을 시작합니다. 완료까지 시간이 소요될 수 있습니다."})

@app.route('/api/pdf/download')
def download_pdf_zip():
    """생성된 PDF ZIP 파일 다운로드"""
    zip_path = scraping_status.get("pdf_zip_path")
    if not zip_path or not os.path.exists(zip_path):
        return jsonify({"status": "error", "message": "다운로드할 PDF 파일이 없습니다. 먼저 PDF 저장을 실행해주세요."})
    
    return send_file(zip_path, as_attachment=True, download_name=os.path.basename(zip_path))

@app.route('/api/pdf/status')
def get_pdf_status():
    """PDF 생성 상태 및 다운로드 준비 여부 확인"""
    return jsonify({
        "has_zip": bool(scraping_status.get("pdf_zip_path") and os.path.exists(scraping_status.get("pdf_zip_path", ""))),
        "zip_filename": os.path.basename(scraping_status.get("pdf_zip_path", "")) if scraping_status.get("pdf_zip_path") else None
    })


def run_pdf_save_task(target_dir_arg=None):
    global scraping_status
    import time
    import re
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader, PdfWriter
    
    batch_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 저장 베이스 디렉토리 설정
    if target_dir_arg:
        base_output_dir = target_dir_arg
    else:
        base_output_dir = os.path.join(OUTPUT_DIR, batch_ts)
    
    if not os.path.exists(base_output_dir):
        os.makedirs(base_output_dir)
    
    def sanitize(text):
        if not text: return ""
        return re.sub(r'[\\/:*?"<>|]', "_", str(text))

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1400, 'height': 900},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            data_list = scraping_status["data"]
            for i, item in enumerate(data_list):
                url = item.get("팝업페이지링크")
                law_group = sanitize(item.get("법령명", "기타"))
                law_name_detail = item.get("법령명_상세", f"법령_{i+1}")
                law_info_meta = item.get("시행/개정", "")
                
                # 파일명용 생협법 약칭 등 처리
                law_filename = sanitize(law_name_detail)
                
                if url and url.startswith("http"):
                    scraping_status["current_category"] = f"[{i+1}/{len(data_list)}] PDF 저장 중: {law_filename}"
                    
                    category_dir = os.path.join(base_output_dir, law_group)
                    if not os.path.exists(category_dir):
                        os.makedirs(category_dir)
                    
                    # 파일명 규칙: {법령명}_{시행일}.pdf
                    impl_date_val = item.get("시행일", "")
                    if not impl_date_val or impl_date_val in ["대기중", "찾을 수 없음"]:
                        impl_date_str = "날짜미입력"
                    else:
                        impl_date_str = sanitize(impl_date_val)
                        
                    pdf_path = os.path.join(category_dir, f"{law_filename}_{impl_date_str}.pdf")
                    
                    try:
                        page = context.new_page()
                        page.goto(url, wait_until="networkidle", timeout=60000)
                        time.sleep(3)  # 페이지 완전 로드 대기
                        
                        content_html = None
                        
                        try:
                            # 1. lawService iframe 접근 시도
                            iframe_element = page.query_selector('iframe#lawService')
                            if iframe_element:
                                frame = iframe_element.content_frame()
                                if frame:
                                    # iframe 로딩 대기
                                    time.sleep(2)
                                    
                                    # 본문 전체 펼치기
                                    try:
                                        fold_btns = frame.query_selector_all('a[onclick*="fold"], a[class*="open"], span:has-text("펼치기")')
                                        for btn in fold_btns[:10]:
                                            try:
                                                btn.click()
                                                time.sleep(0.3)
                                            except:
                                                pass
                                    except:
                                        pass
                                    
                                    # 전체 스크롤
                                    try:
                                        frame.evaluate('''() => {
                                            const scrollContainer = document.getElementById('conScroll') || document.body;
                                            const scrollHeight = scrollContainer.scrollHeight;
                                            let currentPos = 0;
                                            const step = 500;
                                            while (currentPos < scrollHeight) {
                                                scrollContainer.scrollTop = currentPos;
                                                currentPos += step;
                                            }
                                            scrollContainer.scrollTop = 0;
                                        }''')
                                        time.sleep(1)
                                    except:
                                        pass
                                    
                                    # 불필요한 UI 요소 제거
                                    try:
                                        frame.evaluate('''() => {
                                            const removeSelectors = [
                                                'img[alt*="조문체계도"]', 'img[alt*="연혁"]', 'img[alt*="관련규제"]', 'img[alt*="버튼"]',
                                                'a[href*="lsStmdInfoP"]', 'a[href*="lsHstryInfoP"]', 'a[href*="lsLnkInfoP"]',
                                                '.lawnum_btn', '.law_btn', '.btn_area', '.btn_wrap', 'ul.law_link',
                                                '[class*="tooltip"]', '[class*="popup"]',
                                            ];
                                            removeSelectors.forEach(sel => {
                                                document.querySelectorAll(sel).forEach(el => el.remove());
                                            });
                                        }''')
                                    except:
                                        pass
                                    
                                    # 이미지 절대 경로 변환
                                    try:
                                        frame.evaluate('''() => {
                                            const baseUrl = 'https://www.law.go.kr';
                                            document.querySelectorAll('img').forEach(img => {
                                                const src = img.getAttribute('src');
                                                if (src && !src.startsWith('http') && !src.startsWith('data:')) {
                                                    img.setAttribute('src', baseUrl + (src.startsWith('/') ? src : '/' + src));
                                                }
                                            });
                                        }''')
                                    except:
                                        pass
                                    
                                    # 본문 HTML 추출
                                    content_html = frame.evaluate('''() => {
                                        const selectors = ['#conScroll', '#contentBody', '.lawcon', 'article', '.content'];
                                        for (const sel of selectors) {
                                            const el = document.querySelector(sel);
                                            if (el && el.innerHTML.length > 500) {
                                                const clone = el.cloneNode(true);
                                                // 제목 부분은 우리가 직접 HTML로 넣을 것이므로 제거할 수도 있으나, 
                                                // 여기서는 원본 유지하고 상단에 우리 제목을 추가함
                                                return clone.innerHTML;
                                            }
                                        }
                                        return document.body.innerHTML;
                                    }''')
                            
                            if not content_html or len(content_html) < 500:
                                content_html = page.evaluate('''() => {
                                    const selectors = ['#conScroll', '#contentBody', '.lawcon', '#lawService', 'article'];
                                    for (const sel of selectors) {
                                        const el = document.querySelector(sel);
                                        if (el && el.innerText.length > 300) return el.outerHTML;
                                    }
                                    return document.body.outerHTML;
                                }''')
                        
                        except Exception as extract_err:
                            print(f"Content extraction error for {law_filename}: {extract_err}")
                            content_html = None
                        
                        # PDF 생성용 타이틀 구성
                        # 사용자가 요청한 형식: 법령명(약칭) \n [시행...] [법령번호...]
                        display_title_line1 = law_name_detail
                        display_title_line2 = law_info_meta if law_info_meta else f"[시행 {impl_date_val if impl_date_val else '-'}]"
                        full_meta_title = f"{display_title_line1} {display_title_line2}".strip()

                        # PDF 생성
                        if content_html:
                            content_page = context.new_page()
                            styled_html = f'''
                            <!DOCTYPE html>
                            <html>
                            <head>
                                <meta charset="UTF-8">
                                <title>{full_meta_title}</title>
                                <style>
                                    @page {{ margin: 1.5cm; }}
                                    body {{ 
                                        font-family: 'Malgun Gothic', 'Nanum Gothic', 'Noto Sans KR', sans-serif; 
                                        padding: 20px; 
                                        line-height: 1.6;
                                        font-size: 11pt;
                                        color: #333;
                                    }}
                                    .header-container {{
                                        text-align: center;
                                        margin-bottom: 30px;
                                        border-bottom: 2px solid #2563eb;
                                        padding-bottom: 20px;
                                    }}
                                    .law-title-text {{
                                        font-size: 20pt;
                                        font-weight: 800;
                                        margin-bottom: 5px;
                                        color: #1e3a8a;
                                    }}
                                    .law-info-text {{
                                        font-size: 11pt;
                                        color: #666;
                                    }}
                                    table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
                                    td, th {{ border: 1px solid #ccc; padding: 8px; vertical-align: top; }}
                                    img {{ max-width: 100%; height: auto; }}
                                    script, style, iframe, nav, header, footer, .btn, button {{ display: none !important; }}
                                    .law_link, .lawnum_btn, .law_btn, .btn_area, .btn_wrap {{ display: none !important; }}
                                </style>
                            </head>
                            <body>
                                <div class="header-container">
                                    <div class="law-title-text">{display_title_line1}</div>
                                    <div class="law-info-text">{display_title_line2}</div>
                                </div>
                                <div class="content-body">
                                    {content_html}
                                </div>
                            </body>
                            </html>
                            '''
                            content_page.set_content(styled_html, wait_until="load")
                            time.sleep(1)
                            
                            content_page.pdf(
                                path=pdf_path, 
                                format="A4", 
                                print_background=True,
                                margin={'top': '1.5cm', 'right': '1cm', 'bottom': '1.5cm', 'left': '1cm'}
                            )
                            content_page.close()
                            
                            # PDF 메타데이터 설정 (pypdf 사용)
                            try:
                                reader = PdfReader(pdf_path)
                                writer = PdfWriter()
                                for page_obj in reader.pages:
                                    writer.add_page(page_obj)
                                writer.add_metadata({
                                    "/Title": full_meta_title,
                                    "/Subject": "FTC Law Navigator Generated PDF",
                                    "/Producer": "Playwright with pypdf"
                                })
                                with open(pdf_path, "wb") as f:
                                    writer.write(f)
                            except Exception as meta_err:
                                print(f"Metadata update error for {law_filename}: {meta_err}")
                                
                            print(f"  [OK] PDF 저장 완료: {pdf_path}")
                        else:
                            # fallback: 전체 페이지 PDF
                            page.pdf(path=pdf_path, format="A4", print_background=True)
                            print(f"  [FALLBACK] 전체 페이지 PDF 저장: {pdf_path}")
                        
                        page.close()
                    except Exception as e:
                        print(f"PDF creation error for {law_filename}: {e}")
                
                scraping_status["progress"] = i + 1
                time.sleep(0.3)
            
            browser.close()
            
            # ZIP 생성 (사용자가 지정한 폴더가 아닌 경우에만 output 폴더에 ZIP 생성)
            if not target_dir_arg:
                import shutil
                pdf_folder = os.path.join(OUTPUT_DIR, batch_ts)
                if os.path.exists(pdf_folder):
                    zip_path = os.path.join(OUTPUT_DIR, f"FTC_Laws_PDF_{batch_ts}")
                    shutil.make_archive(zip_path, 'zip', pdf_folder)
                    scraping_status["pdf_zip_path"] = zip_path + ".zip"
                    print(f"  [OK] ZIP 파일 생성 완료: {zip_path}.zip")
            
    except Exception as e:
        print(f"PDF save task overall error: {e}")
    finally:
        scraping_status["is_running"] = False
        if target_dir_arg:
            scraping_status["current_category"] = f"PDF 저장 완료! (위치: {base_output_dir})"
        elif scraping_status.get("pdf_zip_path"):
            scraping_status["current_category"] = "PDF 저장 완료! 다운로드 버튼을 클릭하세요."
        else:
            scraping_status["current_category"] = "PDF 저장 완료"

if __name__ == '__main__':
    app.run(debug=True, port=5000)
