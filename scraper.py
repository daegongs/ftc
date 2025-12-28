import requests
from bs4 import BeautifulSoup
import urllib3

# SSL 경고 메시지 무시 설정 (폐쇄망/프록시 환경 대응)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import pandas as pd
import time
import random
import re

# --- Constants ---
BASE_URL = "https://www.ftc.go.kr"
BASE_PAGE_URL = "https://www.ftc.go.kr/www/selectCmitJrsdLawordList.do?key={key}&searchLawordClCd={cd}"
OUTPUT_FILE = "ftc_law_data.xlsx"
SEARCH_LAWORD_CL_CD_START = 1
SEARCH_LAWORD_CL_CD_END = 3

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
]

def fetch_page(url, headers=None, timeout=10, session=None):
    if headers is None:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.ftc.go.kr/www/selectCmitJrsdLawordList.do?key=299",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1"
        }
    try:
        # 403 방지를 위한 미세 지연
        time.sleep(random.uniform(0.5, 1.5))
        
        if session:
            response = session.get(url, headers=headers, timeout=timeout, verify=False)
        else:
            response = requests.get(url, headers=headers, timeout=timeout, verify=False)
        response.raise_for_status()
        
        if response.apparent_encoding and ('euc-kr' in response.apparent_encoding.lower() or 'cp949' in response.apparent_encoding.lower()):
            response.encoding = response.apparent_encoding
        else:
            response.encoding = 'utf-8'
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return None

def scrape_ftc_law_data(search_laword_cl_cd):
    all_law_data = []
    session = requests.Session()
    
    # FTC 사이트의 실제 key 값 매핑 (select box value → API key)
    KEY_MAPPING = {
        1: 299,   # 공정거래법
        2: 300,   # 하도급법
        3: 301,   # 약관법
        4: 302,   # 표시광고법
        5: 303,   # 할부거래법
        6: 304,   # 방문판매법
        7: 305,   # 전자상거래법
        8: 306,   # 대규모유통업법
        9: 307,   # 가맹사업법
        10: 309,  # 소비자기본법 (key=309)
        11: 308,  # 대리점법 (key=308)
        12: 310,  # 생협법 (key=310)
        13: 311,  # 제조물책임법 (key=311)
        14: 312,  # 기타 (key=312)
    }
    
    # FTC 사이트의 searchLawordClCd 매핑 (select box value → URL의 cd 파라미터)
    CD_MAPPING = {
        1: 1,     # 공정거래법
        2: 2,     # 하도급법
        3: 3,     # 약관법
        4: 4,     # 표시광고법
        5: 5,     # 할부거래법
        6: 6,     # 방문판매법
        7: 7,     # 전자상거래법
        8: 8,     # 대규모유통업법
        9: 9,     # 가맹사업법
        10: 10,   # 소비자기본법
        11: 12,   # 대리점법 (searchLawordClCd=12)
        12: 13,   # 생협법 (searchLawordClCd=13)
        13: 14,   # 제조물책임법 (searchLawordClCd=14)
        14: 11,   # 기타 (searchLawordClCd=11)
    }
    
    cd_int = int(search_laword_cl_cd)
    key_val = KEY_MAPPING.get(cd_int, 298 + cd_int)  # 매핑에 없으면 기존 방식
    cd_val = CD_MAPPING.get(cd_int, cd_int)  # searchLawordClCd 매핑
    main_page_url = BASE_PAGE_URL.format(key=key_val, cd=f"{cd_val:02d}")
    
    print(f"\nProcessing: {main_page_url}")
    main_soup = fetch_page(main_page_url, session=session)
    if not main_soup: return pd.DataFrame()

    # 카테고리명 추출
    category_name = ""
    colgroup_header = main_soup.select_one("#colgroup > header > h2") or main_soup.select_one("h2")
    if colgroup_header:
        category_name = colgroup_header.get_text(strip=True)

    # 테이블 추출
    table = main_soup.select_one("div.tbl-wrap table") or main_soup.find('table')
    if not table: return pd.DataFrame()

    tbody = table.find('tbody')
    rows = tbody.find_all('tr') if tbody else table.find_all('tr')
    
    # 헤더 제외 데이터 행 필터링 (구분 열이 th인 경우가 많으므로 th 필터링 제거)
    data_rows = [row for row in rows if row.find('td')] # 최소한 td가 하나라도 있는 행만 포함
    
    # 셀 병합(rowspan) 추적용 캐시
    rowspan_cache = {} # {col_idx: {"count": n, "value": td_element}}

    for i, row in enumerate(data_rows):
        law_entry = {
            "법령명": category_name,
            "구분": "",
            "법령명_상세": "",
            "담당부서": "",
            "시행/개정": "",
            "팝업페이지링크": ""
        }

        # td와 th 태그 모두 수집 (공정위는 구분 열에 th를 쓰는 경우가 많음)
        cells = row.find_all(['td', 'th'])
        cell_ptr = 0
        logical_cols = []
        
        # 논리적 컬럼 구조 (0:구분, 1:법령명_상세, 2:담당부서)
        for col_idx in range(3):
            # 이전 행에서 병합된(rowspan) 데이터가 있는지 확인
            if col_idx in rowspan_cache and rowspan_cache[col_idx]["count"] > 0:
                logical_cols.append(rowspan_cache[col_idx]["value"])
                rowspan_cache[col_idx]["count"] -= 1
            else:
                # 병합된 게 없다면 현재 행의 셀에서 가져옴
                if cell_ptr < len(cells):
                    cell = cells[cell_ptr]
                    logical_cols.append(cell)
                    
                    # 새로운 rowspan 예약
                    rs_val = cell.get('rowspan')
                    rs = int(rs_val) if rs_val and rs_val.isdigit() else 1
                    if rs > 1:
                        rowspan_cache[col_idx] = {"count": rs - 1, "value": cell}
                    cell_ptr += 1
                else:
                    logical_cols.append(None)

        # 데이터 매핑 (인덱스 보장)
        def get_val(obj):
            if not obj: return ""
            return obj.get_text(strip=True) if hasattr(obj, 'get_text') else str(obj)

        law_entry["구분"] = get_val(logical_cols[0])
        law_entry["담당부서"] = get_val(logical_cols[2])
        
        # 법령명 상세 및 링크 추출 (logical_cols[1])
        name_cell = logical_cols[1]
        if name_cell and hasattr(name_cell, 'find'):
            law_entry["법령명_상세"] = name_cell.get_text(strip=True)
            a_tag = name_cell.find('a')
            if a_tag:
                href = a_tag.get('href', '')
                if href.startswith('/'): detail_url = BASE_URL + href
                elif 'javascript:' in href:
                    match = re.search(r"['\"]([^'\"]+)['\"]", a_tag.get('onclick', ''))
                    detail_url = BASE_URL + match.group(1) if match else "N/A"
                else: detail_url = href if href.startswith('http') else BASE_URL + '/' + href
                
                law_entry["팝업페이지링크"] = detail_url
                # 상세 페이지 수집은 app.py의 별도 태스크에서 처리하므로 초기에는 대기중으로 설정
                law_entry["시행일"] = "대기중"
                law_entry["개정유형"] = "대기중"
                law_entry["개정정보"] = "대기중"
                law_entry["개정일"] = "대기중"
                law_entry["시행/개정"] = "대기중"
            else:
                law_entry["팝업페이지링크"] = "N/A"
                law_entry["시행일"] = "N/A"
                law_entry["개정유형"] = "-"
                law_entry["개정정보"] = "-"
                law_entry["개정일"] = "-"
                law_entry["시행/개정"] = "N/A"
        
        all_law_data.append(law_entry)

    return pd.DataFrame(all_law_data)

if __name__ == "__main__":
    all_dfs = []
    for cd in range(SEARCH_LAWORD_CL_CD_START, SEARCH_LAWORD_CL_CD_END + 1):
        df = scrape_ftc_law_data(cd)
        if not df.empty: all_dfs.append(df)
        time.sleep(1)
        
    if all_dfs:
        final_df = pd.concat(all_dfs, ignore_index=True)
        cols = ["법령명", "구분", "법령명_상세", "담당부서", "시행/개정", "팝업페이지링크"]
        final_df = final_df[[c for c in cols if c in final_df.columns]]
        final_df.to_excel(OUTPUT_FILE, index=False)
        print(f"\nSaved {len(final_df)} entries to {OUTPUT_FILE}")