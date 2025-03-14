import requests
import configparser
import os
import re
import sqlite3
from datetime import datetime
import logging
from openai import OpenAI

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 설정 파일 로드
def load_config():
    config = configparser.ConfigParser()
    config.read("config.ini")
    return config

config = load_config()
FRESHDESK_DOMAIN = config["Freshdesk"]["Domain"]
FRESHDESK_API_KEY = config["Freshdesk"]["APIKey"]
OPENAI_API_KEY = config["OpenAI"]["APIKey"]
VECTOR_STORAGE_ID = config["OpenAI"]["VectorStorageID"] # 벡터 저장소 ID
CATEGORY_NAME = "Frequently Asked Questions"
# TARGET_FOLDERS = {
#     "New Features",
#     "Connection",
#     "Device",
#     "Server",
#     "User",
#     "Card",
#     "Wiegand",
#     "Settings"
# }

TARGET_FOLDERS = [
                    "New Features", "Connection", "Device", "Server", 
                    "User", "Card", "Wiegand", "Settings", "T&A", "Report", 
                    "BioStar 2 API (Current API)", "BioStar 2 TA API", "Visitor", "General"
                ]
FILTER_DATE = datetime.strptime("2000-02-01T00:00:00Z", "%Y-%m-%dT%H:%M:%SZ") # 필터 날짜 설정

# Freshdesk API URL 설정
BASE_URL = f"https://{FRESHDESK_DOMAIN}/api/v2/solutions"
HEADERS = {"Content-Type": "application/json"}
AUTH = (FRESHDESK_API_KEY, "X")

# SQLite DB 설정
db_path = "attachments.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 파일 이름 정리 함수
def sanitize_filename(filename):
    return re.sub(r'[\\/:*?"<>|\[\]]', '_', filename)

# 카테고리 ID 찾기
def get_category_id():
    response = requests.get(f"{BASE_URL}/categories", auth=AUTH, headers=HEADERS)
    response.raise_for_status()
    categories = response.json()

    for category in categories:
        if category["name"] == CATEGORY_NAME:
            return category["id"]
    return None

# 폴더 ID 찾기
def get_folder_ids(category_id):
    response = requests.get(f"{BASE_URL}/categories/{category_id}/folders", auth=AUTH, headers=HEADERS)
    response.raise_for_status()
    folders = response.json()

    folder_ids = {}
    for folder in folders:
        if folder["name"] in TARGET_FOLDERS:
            folder_ids[folder["name"]] = folder["id"]
    return folder_ids

# 특정 폴더 내 문서 가져오기 (필터링 제거)
def get_articles(folder_id):
    page = 1
    per_page = 100
    all_articles = []
    while True:
        print(f"Page: {page}")
        url = f"{BASE_URL}/folders/{folder_id}/articles?page={page}&per_page={per_page}"
        response = requests.get(url,  headers=HEADERS, auth=AUTH)

        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            break
        
        articles = response.json()
        if not articles:
            break
        all_articles.extend(articles)
        
        page += 1
    return all_articles

# MD 파일로 저장 & DB 저장
def save_as_markdown(articles):
    base_path = os.path.join("docs")
    os.makedirs(base_path, exist_ok=True)
    total_count = 0
    file_id_list = []

    for article in articles:
        updated_at = datetime.strptime(article['updated_at'], "%Y-%m-%dT%H:%M:%SZ")
        if updated_at < FILTER_DATE:
            logging.debug(f"문서 ID {article['id']}는 필터 조건에 맞지 않아 건너뜁니다.")
            continue

        safe_title = sanitize_filename(article['title'])
        file_path = os.path.join(base_path, f"{safe_title}.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# {article['title']}\n\n")
            f.write(article['description'])

        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        cursor.execute("SELECT COUNT(*) FROM attachments WHERE file_id = ?", (article['id'],))
        count = cursor.fetchone()[0]

        if count > 0:
            logging.debug(f"file_id {article['id']} already exists. Updating updated_at, name, created_at.")
            cursor.execute("""
                UPDATE attachments SET updated_at = ?, name = ?, created_at = ? WHERE file_id = ?
            """, (now, article['title'], article['created_at'], article['id']))
        else:
            logging.debug(f"file_id {article['id']} does not exist. Inserting new record.")
            cursor.execute("""
                INSERT INTO attachments (file_id, name, created_at, updated_at, openai_file_id)
                VALUES (?, ?, ?, ?, NULL)
            """, (article['id'], article['title'], article['created_at'], now))
        file_id_list.append({"freshdesk_file_id": article['id'], "file_path": file_path})
        conn.commit()
        total_count += 1

    return total_count, file_id_list

# OpenAI 벡터 저장소 업데이트
# OpenAI 벡터 저장소 업데이트
def update_openai_vector_store(file_id_list):
    updated_file_ids = []
    client = OpenAI(api_key=OPENAI_API_KEY)

    for file_info in file_id_list:
        freshdesk_file_id = file_info["freshdesk_file_id"]
        file_path = file_info["file_path"]

        cursor.execute("SELECT openai_file_id FROM attachments WHERE file_id = ?", (freshdesk_file_id,))
        result = cursor.fetchone()
        openai_file_id = result[0] if result else None

        if openai_file_id:
            try:
                client.vector_stores.files.delete(
                    vector_store_id=VECTOR_STORAGE_ID,
                    file_id=openai_file_id
                )
                client.files.delete(openai_file_id)
                logging.info(f"File ID {freshdesk_file_id}: 기존 파일 삭제 후 재업로드")
            except Exception as e:
                logging.error(f"File ID {freshdesk_file_id}: 기존 파일 삭제 오류 - {e}")

        try:
            with open(file_path, "rb") as f:
                openai_file_id = client.files.create(file=f, purpose="assistants").id
                logging.info(f"File ID {freshdesk_file_id}: 파일 업로드 완료, OpenAI File ID: {openai_file_id}")

                try:
                    client.vector_stores.files.create(
                        vector_store_id=VECTOR_STORAGE_ID,
                        file_id=openai_file_id
                    )
                    logging.info(f"File ID {freshdesk_file_id}: 벡터 저장소 연결 완료")
                except Exception as e:
                    logging.error(f"File ID {freshdesk_file_id}: 벡터 저장소 연결 오류 - {e}")

                updated_file_ids.append((freshdesk_file_id, openai_file_id))
        except Exception as e:
            logging.error(f"File ID {freshdesk_file_id}: 파일 업로드 오류 - {e}")
    return updated_file_ids


# 실행 로직
if __name__ == "__main__":
    category_id = get_category_id()
    if not category_id:
        print("❌ 지정한 카테고리를 찾을 수 없습니다.")
        exit(1)

    folder_ids = get_folder_ids(category_id)
    if not folder_ids:
        print("❌ 지정한 폴더를 찾을 수 없습니다.")
        exit(1)

    total_articles = 0
    all_file_ids = []

    for folder_name, folder_id in folder_ids.items():
        articles = get_articles(folder_id)
        if articles:
            count, file_id_list = save_as_markdown(articles)
            total_articles += count
            all_file_ids.extend(file_id_list)

    print(f" 전체 문서 다운로드 완료! 총 {total_articles}개의 문서 저장됨.")

    updated_file_ids = update_openai_vector_store(all_file_ids)

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    for file_id, openai_file_id in updated_file_ids:
        cursor.execute("UPDATE attachments SET openai_file_id = ?, updated_at = ? WHERE file_id = ?", (openai_file_id, now, file_id))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM attachments")
    total_db_records = cursor.fetchone()[0]
    print(f" DB 저장 문서 개수: {total_db_records}")
    conn.close()