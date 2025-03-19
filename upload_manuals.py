import os
import logging
import configparser
import sqlite3
from datetime import datetime, timezone
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config():
    config = configparser.ConfigParser()
    config.read("config.ini")
    return config


config = load_config()
OPENAI_API_KEY = config["OpenAI"]["APIKey"]
VECTOR_STORAGE_ID = config["OpenAI"]["VectorStorageID_local"]

db_path = "attachments.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

client = OpenAI(api_key=OPENAI_API_KEY)

def upload_manuals():
    manuals_dir = "manuals_test"
    if not os.path.exists(manuals_dir):
        logging.error(f"Directory {manuals_dir} does not exist")
        return
    
    uploaded_count = 0
    
    for manual_file in os.listdir(manuals_dir):
        file_path = os.path.join(manuals_dir, manual_file)
        if not os.path.isfile(file_path):
            continue

        file_id = f"manual_{manual_file}"

        # check if file is already uploaded to OpenAI
        cursor.execute("SELECT openai_file_id FROM manuals WHERE file_id = ?", (file_id,))
        result = cursor.fetchone()
        openai_file_id = result[0] if result else None
        
        # delete existing file if it exists
        if openai_file_id:
            print(f"File {manual_file}: {openai_file_id}")
            try:
                client.vector_stores.files.delete(
                    vector_store_id=VECTOR_STORAGE_ID,
                    file_id=openai_file_id
                )
                client.files.delete(openai_file_id)
                logging.info(f"File {manual_file}: Deleted from OpenAI")
            except Exception as e:
                logging.error(f"File {manual_file}: Deleted from OpenAI error - {e}")
                
        # upload file to OpenAI
        try:
            with open(file_path, "rb") as f:
                openai_file_id = client.files.create(file=f, purpose="assistants").id
                logging.info(f"File {manual_file}, {openai_file_id}: Uploaded to OpenAI")
                

                # connect to vector store
                try:
                    client.vector_stores.files.create(
                        vector_store_id=VECTOR_STORAGE_ID,
                        file_id=openai_file_id
                    )
                    logging.info(f"File {manual_file}: Connected to vector store")

                    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")     

                    if result:
                        cursor.execute("""
                                    UPDATE manuals SET openai_file_id = ?, updated_date = ? WHERE file_id = ?
                                """, (openai_file_id, now, file_id))
                    else:
                        cursor.execute("""
                                    INSERT INTO manuals (file_id, title, updated_date, openai_file_id)
                                    VALUES (?, ?, ?, ?)
                                """, (file_id, manual_file, now, openai_file_id))
                        
                    conn.commit()
                    logging.info(f"File {manual_file}: Updated in database")
                    uploaded_count += 1


                except Exception as e: 
                    logging.error(f"File {manual_file}: Connected to vector store error - {e}")
                    
        except Exception as e:
            logging.error(f"File {manual_file}: Connection error with OpenAI - {e}")
        if uploaded_count % 10 == 0:
            print(f"{uploaded_count} files uploadedso far")

    logging.info(f"Total files uploaded: {uploaded_count}")

if __name__ == "__main__":
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS manuals (
        file_id TEXT PRIMARY KEY,
        title TEXT,
        updated_date TEXT,
        openai_file_id TEXT UNIQUE
    )
    """)
    conn.commit()
    upload_manuals()
    conn.close()


# file-HmkmJF3TksQUKDkqA75yY8






