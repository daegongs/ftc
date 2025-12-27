# -*- coding: utf-8 -*-
# 필요한 라이브러리를 불러옵니다.
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from urllib.parse import urljoin
import time
from datetime import datetime
import os

# --- 설정 ---
base_url = "https://www.ftc.go.kr/"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# 검색 조건 설정
search_conditions = {
    'bordCd': '3',  # 보도자료 게시판
    'key': '12',  # 보도자료 게시판 키
    'searchCtgry': '02',  # 참고자료 (01,02: 전체, 01: 보도, 02: 참고)
    'searchCnd': 'all',  # 전체 검색
    'searchKrwd': '',  # 검색어
    'pageUnit': '10',  # 페이지당 표시 개수
    'searchPd': '5'  # 기간 설정 (1:직접입력, 2:1개월, 3:3개월, 4:6개월, 5:1년)
}

# 기본 스크래핑 URL 구성
base_scrape_url = f"{base_url}www/selectBbsNttList.do"
start_page = 1
end_page = 2 # 크롤링할 마지막 페이지 --> 사이트 부담을 줄이기 위해 end_page 페이지로 제한

def get_article_content(session, article_url):
    """게시글 상세 페이지에서 본문 내용을 추출합니다."""
    try:
        response = session.get(article_url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 본문 내용이 있는 요소 찾기 (선택자 순서 변경 및 추가)
        content_div = soup.find(class_='p-table__content') # 가장 먼저 시도
        if not content_div:
            content_div = soup.find('div', class_='bbs_view_content') 
        if not content_div:
            content_div = soup.find('div', class_='view_cont')
            
        if content_div:
            # 본문 내용에서 불필요한 태그 제거 및 텍스트 정리
            content = content_div.get_text(strip=True, separator=' ') # separator를 공백으로 변경
            # 추가적인 줄바꿈 문자 처리 (혹시 남아있을 경우 대비)
            content = content.replace('\n', ' ').strip()
            return content
        else:
            print(f"본문을 찾을 수 없습니다 (p-table__content, bbs_view_content, view_cont 시도): {article_url}")
            return ""
    except Exception as e:
        print(f"본문 가져오기 실패: {article_url} - {str(e)}")
        return ""

# --- 전체 페이지 수 가져오기 함수 (수정됨) ---
def get_total_pages(url, headers):
    """주어진 URL의 첫 페이지에서 전체 페이지 수를 추출합니다."""
    try:
        # 세션 생성
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        # 디버깅을 위해 HTML 구조를 출력
        print("HTML 구조 확인 중...")
        print(f"검색 URL: {url}")
        
        # 페이지 번호 영역을 찾습니다.
        pagination_div = soup.find('div', class_='paging')
        if not pagination_div:
            pagination_div = soup.find('div', class_='page_num')
        if not pagination_div:
            pagination_div = soup.find('div', class_='pagination')
        if not pagination_div:
            pagination_div = soup.find('div', class_='paging_area')

        # 페이지 번호 영역을 찾았는지 확인합니다.
        if not pagination_div:
            print("페이지 번호 영역을 찾을 수 없습니다. HTML 구조를 확인합니다...")
            print(soup.prettify()[:1000])  # HTML의 처음 1000자만 출력
            return 1

        # 페이지 번호 영역 내의 모든 링크(<a> 태그)를 찾습니다.
        page_links = pagination_div.find_all('a')
        
        # 링크들을 역순으로 탐색합니다.
        if page_links:
            for link in reversed(page_links):
                link_text = link.get_text(strip=True)
                if link_text.isdigit():
                    return int(link_text)

        # 숫자 링크를 찾지 못한 경우
        current_page_tag = pagination_div.find('strong')
        if current_page_tag:
            current_page_text = current_page_tag.get_text(strip=True)
            if current_page_text.isdigit():
                return int(current_page_text)

        print("페이지 번호를 찾지 못했습니다. 1페이지로 가정합니다.")
        return 1

    except requests.exceptions.RequestException as e:
        print(f"전체 페이지 수를 가져오는 중 오류 발생: {e}")
        return 1
    except Exception as e:
        print(f"페이지 수 분석 중 오류 발생: {e}")
        return 1

# --- 메인 스크래핑 로직 ---
# URL 파라미터 구성
url_params = '&'.join([f"{k}={v}" for k, v in search_conditions.items()])
first_page_url = f"{base_scrape_url}?{url_params}&pageIndex=1"
total_pages = get_total_pages(first_page_url, headers)

if total_pages:
    print(f"총 페이지 수: {total_pages}")
else:
    print("총 페이지 수를 가져올 수 없어 스크래핑을 중단합니다.")
    exit()

# --- 이하 스크래핑 로직은 이전과 동일 ---
all_data_list = []
session = requests.Session()  # 세션 생성
print(f"\n--- {start_page}페이지부터 {end_page}페이지까지 데이터 스크래핑 시작 ---")
for page_num in range(start_page, end_page + 1):
    page_url = f"{base_scrape_url}?{url_params}&pageIndex={page_num}"
    print(f"[{page_num}/{end_page}] 페이지 스크래핑 중: {page_url}")
    try:
        response = session.get(page_url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        table_body = soup.find('tbody')
        if not table_body:
            print(f"   경고: {page_num}페이지에서 테이블 본문(tbody)을 찾을 수 없습니다.")
            continue
        rows = table_body.find_all('tr')
        if not rows:
            print(f"  정보: {page_num}페이지에 데이터가 없습니다.")
            continue
        for row in rows:
            cells = row.find_all('td')
            if len(cells) == 6:
                number = cells[0].get_text(strip=True)
                category = cells[1].get_text(strip=True)
                title_link = cells[2].find('a')
                title = title_link.get_text(strip=True) if title_link else cells[2].get_text(strip=True)
                
                # 상세 페이지 URL 가져오기
                article_url = ""
                if title_link:
                    href = title_link.get('href', '')
                    if href:
                        if href.startswith('./'):
                            href = href[2:]  # './' 제거
                        article_url = urljoin(base_url + "www/", href)
                        # 본문 내용 가져오기
                        print(f"  - 본문 가져오는 중: {title}")
                        content = get_article_content(session, article_url)
                    else:
                        content = ""
                else:
                    content = ""
                
                department = cells[3].get_text(strip=True)
                date = cells[4].get_text(strip=True)
                attachment_cell = cells[5]
                attachment_url = '없음'
                link_tag = attachment_cell.find('a')
                if link_tag:
                    onclick_attr = link_tag.get('onclick')
                    href_attr = link_tag.get('href')
                    if onclick_attr and 'fn_bbsFileDown' in onclick_attr:
                        match = re.search(r"fn_bbsFileDown\('(\d+)'\)", onclick_attr)
                        if match:
                            file_number = match.group(1)
                            dl_url_base = "https://www.ftc.go.kr/viewer/www/downloadBbsFileAll.do?atchmnflNo="
                            attachment_url = dl_url_base + file_number
                    elif href_attr and 'downloadBbsFileAll.do' in href_attr:
                        attachment_url = urljoin(base_url, href_attr.strip())
                
                # 본문 내용을 포함하여 데이터 리스트에 추가
                all_data_list.append([number, category, title, department, date, attachment_url, content])
            else:
                pass
            
            # 서버 부하를 줄이기 위해 각 게시글 처리 후 잠시 대기
            time.sleep(0.5)
            
    except requests.exceptions.RequestException as e:
        print(f"  오류: {page_num}페이지를 가져오는 중 오류 발생: {e}")
    except Exception as e:
        print(f"  오류: {page_num}페이지 처리 중 오류 발생: {e}")
    
    # 페이지 간 대기 시간
    time.sleep(1)

print(f"\n--- 총 {len(all_data_list)}개의 데이터 스크래핑 완료 ---")
if all_data_list:
    headers_list = ['번호', '구분', '제목', '담당부서', '등록일', '첨부파일', '본문']
    df = pd.DataFrame(all_data_list, columns=headers_list)
    
    # DataFrame 출력 (기존)
    print(f"\n--- 공정거래위원회 보도자료 스크래핑 결과 ({start_page}-{end_page} 페이지) ---")
    print(df.to_string(index=False))
    
    # output 폴더 생성
    output_dir = 'output'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # CSV 파일로 저장
    # 현재 시간으로 파일명 생성 (YYYYMMDD_HHMMSS 형식)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = os.path.join(output_dir, f'공정위_보도자료_{timestamp}.csv')
    try:
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"\n--- 스크래핑 결과를 '{csv_filename}' 파일로 저장했습니다. ---")
    except Exception as e:
        print(f"\n--- CSV 파일 저장 중 오류 발생: {e} ---")

else:
    print("스크래핑된 데이터가 없습니다.")