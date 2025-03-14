import os
import logging
import configparser
import sqlite3
from datetime import datetime, timezone
from openai import OpenAI

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 설정 파일 로드
def load_config():
    config = configparser.ConfigParser()
    config.read("config.ini")
    return config

config = load_config()
OPENAI_API_KEY = config["OpenAI"]["APIKey"]
VECTOR_STORAGE_ID = config["OpenAI"]["VectorStorageID"]
# VECTOR_STORAGE_ID = "vs_67d42c39ca3881919f7737076d68341f"

# SQLite DB 설정
db_path = "attachments.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# KB 파일 업로드 함수
def upload_kb_files():
    kb_dir = "kb_files"
    if not os.path.exists(kb_dir):
        logging.error(f"Directory {kb_dir} does not exist")
        return
    
    # 디렉토리 내 모든 파일 가져오기
    files = [f for f in os.listdir(kb_dir) if os.path.isfile(os.path.join(kb_dir, f))]
    
    if not files:
        logging.info(f"No files found in {kb_dir}")
        return
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    uploaded_count = 0
    
    for file_name in files:
        file_path = os.path.join(kb_dir, file_name)
        file_id = f"kb_{file_name}"  # 고유 ID 생성
        
        # 이미 업로드된 파일인지 확인
        cursor.execute("SELECT openai_file_id FROM kb_files WHERE file_id = ?", (file_id,))
        result = cursor.fetchone()
        openai_file_id = result[0] if result else None
        
        # 기존 파일이 있으면 삭제
        if openai_file_id:
            try:
                client.vector_stores.files.delete(
                    vector_store_id=VECTOR_STORAGE_ID,
                    file_id=openai_file_id
                )
                client.files.delete(openai_file_id)
                logging.info(f"File {file_name}: 기존 파일 삭제 후 재업로드")
            except Exception as e:
                logging.error(f"File {file_name}: 기존 파일 삭제 오류 - {e}")
        
        # 파일 업로드
        try:
            with open(file_path, "rb") as f:
                openai_file_id = client.files.create(file=f, purpose="assistants").id
                logging.info(f"File {file_name}: 파일 업로드 완료, OpenAI File ID: {openai_file_id}")
                
                # 벡터 저장소에 연결
                try:
                    client.vector_stores.files.create(
                        vector_store_id=VECTOR_STORAGE_ID,
                        file_id=openai_file_id
                    )
                    logging.info(f"File {file_name}: 벡터 저장소 연결 완료")
                    
                    # DB 업데이트
                    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    if result:
                        cursor.execute("""
                            UPDATE kb_files SET openai_file_id = ?, updated_date = ? WHERE file_id = ?
                        """, (openai_file_id, now, file_id))
                    else:
                        cursor.execute("""
                            INSERT INTO kb_files (file_id, title, updated_date, openai_file_id)
                            VALUES (?, ?, ?, ?)
                        """, (file_id, file_name, now, openai_file_id))
                    
                    conn.commit()
                    uploaded_count += 1
                    
                except Exception as e:
                    logging.error(f"File {file_name}: 벡터 저장소 연결 오류 - {e}")
        
        
                    
        except Exception as e:
            logging.error(f"File {file_name}: 파일 업로드 오류 - {e}")
        if uploaded_count % 10 == 0:
            print(f"총 {uploaded_count} so far")
    
    logging.info(f"총 {uploaded_count}개 파일 업로드 완료")
    return uploaded_count

if __name__ == "__main__":
    # 테이블이 없으면 생성
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kb_files (
        file_id TEXT PRIMARY KEY,
        title TEXT,
        updated_date TEXT,
        openai_file_id TEXT UNIQUE
    )
    """)
    conn.commit()
    
    upload_kb_files()
    conn.close()
