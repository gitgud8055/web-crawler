import uuid
from hdfs import InsecureClient
from typing import Dict
import json, re, csv
import pandas as pd
import base64

import concurrent.futures
    
from bs4 import BeautifulSoup
from cassandra.cluster import Cluster

import numpy as np
from sentence_transformers import SentenceTransformer

from confluent_kafka import Consumer
from __init__ import Response

# Kafka configuration
conf = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'file-group',
    'auto.offset.reset': 'earliest'
}
topic = 'html'
consumer = Consumer(conf)
consumer.subscribe([topic])
print("[Consumer] Connected to Kafka!")

# HDFS configuration
hdfs_client = InsecureClient('http://localhost:9870', user='hdfs')
hdfs_path = '/html/'
print("[Consumer] Connected to namenode!")

# Cassandra session 
cluster = Cluster(['localhost'], port=9042)
session = cluster.connect()

cassandra_tablename = "documents"
keyspace = "chatbot"
# create keyspace
session.execute("""
CREATE KEYSPACE IF NOT EXISTS chatbot
  WITH REPLICATION = { 
   'class' : 'SimpleStrategy', 
   'replication_factor' : 1
  };
""").one()

session.set_keyspace(keyspace)
session.execute("""
CREATE TABLE IF NOT EXISTS chatbot.documents(
    id text,
    url text,
    chunk text,
    embed text,
    offset int,
    PRIMARY KEY (id)
   );
""").one()

session.execute("""
CREATE TABLE IF NOT EXISTS chatbot.crawlers(
    id text,
    document_id text,
    user_id text,
    PRIMARY KEY (id)
);
""").one()

session.execute("CREATE INDEX IF NOT EXISTS ON chatbot.crawlers(user_id);").one()

# Retriver config
retriever_model="all-MiniLM-L6-v2"
retriever = SentenceTransformer(retriever_model)

# Received Message
# class Response:
#     url: str
#     timestamp: str
#     html: str
#     userId: str
        
#     def __init__(self, response: Dict):
#         self.url = response["url"]
#         self.timestamp = response["timestamp"]
#         self.html = response["html"]  
#         self.userId = response["userId"]
#         self.json = json.dumps(self.to_dict()) 

#     def to_dict(self):
#         return dict(url=self.url,
#                     timestamp=self.timestamp,
#                     html=self.html,
#                     userId=self.userId)

def dict_to_response(obj):
    if obj is None:
        return None
    obj = json.loads(obj)
    
    return Response(response=obj)    

def extract_content(html_file):
    soup = BeautifulSoup(html_file, 'html.parser')

    for script in soup(["script", "style", "footer", "header", "nav"]):
        script.decompose()

    content = soup.find('div', {'id': 'content'}) or soup.body
    text = content.get_text(separator='\n', strip=True) if content else ''

    return text

def clean_text(text):
    text = re.sub(r'\\t', ' ', text)
    text = re.sub(r'\\n', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\[\d+\]', '', text)

    return text.strip()
            
def sliding_window_chunking(text, max_tokens=512, overlap=128):
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_tokens - overlap):
        chunk = " ".join(words[i:i + max_tokens])
        chunks.append(chunk)
    return chunks

def embed_text(clean_content):
    chunked_contents = []
    encoded_embeddings = []
    
    chunks = sliding_window_chunking(clean_content)
    chunked_contents.extend(chunks)
    embeddings = retriever.encode(chunked_contents)
    
    for embedding in embeddings:
        bin_embedding = embedding.dumps()
        encoded_embedding = base64.b64encode(bin_embedding).decode("utf-8")
        encoded_embeddings.append(encoded_embedding)
        
    return chunked_contents, encoded_embeddings

def process_html(file, user_id = ""):
    if hdfs_client.content(hdfs_path + file, strict=False) is None:
        return
    
    if not file.endswith(".html"):
        return
    
    url = file[:-5]
    
    with hdfs_client.read(hdfs_path + file, encoding='utf-8') as reader:
        html = reader.read()

    extracted_text = extract_content(str(html))
    print("Extracted!")
    clean_extracted_text = clean_text(extracted_text)
    print("Clean!")    
    chunks, embeds = embed_text(clean_extracted_text)
    print("Embed!")
    
    for offset, chunk in enumerate(chunks):
        data = {
            "id": f"{url}_{offset}",
            "url": url,
            "chunk": chunk,
            "embed": embeds[offset],
            "offset": offset
        }
        json_data = json.dumps(data)
        escaped_json_data = re.sub(r"'", "''", json_data)
        
        crawlers = {
            "id": str(uuid.uuid4()),
            "document_id": f"{url}_{offset}",
            "user_id": user_id,
        }
        json_crawlers = json.dumps(crawlers)
        escaped_json_crawlers = re.sub(r"'", "''", json_crawlers)
        
        query = f"INSERT INTO {cassandra_tablename} JSON '{escaped_json_data}';"
        query1 = f"INSERT INTO crawlers JSON '{escaped_json_crawlers}';"
        
        insert_query = session.execute_async(query)
        insert_crawler = session.execute_async(query1)
        def onInsertSuccess(_, offset, tablename):
            print("Insert {} offset {} into {}".format(url, offset, tablename))
        insert_query.add_callback(lambda _, offset=offset, tablename=cassandra_tablename: onInsertSuccess(_, offset, tablename))
        
def process_all_html():
    if hdfs_client.content(hdfs_path, strict=False) is None:
        return
    
    files = hdfs_client.list(hdfs_path)
    print(files)
    for file in files:
        if not file.endswith(".html"):
            continue
        
        url = file[:-5]
        
        with hdfs_client.read(hdfs_path + file, encoding='utf-8') as reader:
            html = reader.read()

        extracted_text = extract_content(str(html))
        print("Extracted!")
        clean_extracted_text = clean_text(extracted_text)
        print("Clean!")    
        chunks, embeds = embed_text(clean_extracted_text)
        print("Embed!")
        
        for offset, chunk in enumerate(chunks):
            data = {
                "id": f"{url}_{offset}",
                "url": url,
                "chunk": chunk,
                "embed": embeds[offset],
                "offset": offset
            }
            json_data = json.dumps(data)
            escaped_json_data = re.sub(r"'", "''", json_data)
            
            query = f"INSERT INTO {cassandra_tablename} JSON '{escaped_json_data}';"
            result = session.execute_async(query)
            def onSuccess(_, offset, tablename):
                print("Insert {} offset {} into {}".format(url, offset, tablename))
            def onFail(_, offset):
                print("Failed at {} offset {}".format(url, offset))
            result.add_callback(lambda _, offset=offset, tablename=cassandra_tablename: onSuccess(_, offset, tablename))
            result.add_errback(lambda _, offset=offset: onFail(_, offset))
            
            
            
def add_log(url, timestamp, log_hdfs_path):

    if hdfs_client.content(log_hdfs_path, strict=False) is not None:
        with hdfs_client.read(log_hdfs_path, encoding='utf-8') as reader:
            hdfs_df = pd.read_csv(reader)
    else:
        hdfs_df = pd.DataFrame(columns=["url", "timestamp"])

    if url in hdfs_df["url"].values:
        hdfs_df.loc[hdfs_df["url"] == url, "timestamp"] = timestamp
    else:
        hdfs_df = pd.concat([hdfs_df, pd.DataFrame([[url, timestamp]], columns=["url", "timestamp"])], ignore_index=True)
        
    with hdfs_client.write(log_hdfs_path, encoding='utf-8', overwrite=True) as writer:
        hdfs_df.to_csv(writer, index=False)


# Consume and HDFS
def consume_and_save():
    while True:
        msg = consumer.poll(1.0)  # Timeout in seconds
        if msg is None:
            continue
        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue
        
        response = dict_to_response(msg.value())
        
        if response is not None:
            print("Fetch {}: url {}: \ttimestamp: {}\n"
                      .format(msg.key(), response.url,
                              response.timestamp))
            
            url_path = re.sub(r'^https?://', '', response.url)
            url_path = re.sub(r'[<>:"/\\|?*]', '_', url_path)
                        
            html_hdfs_path = hdfs_path + "/" + url_path + ".html"
            
            print("Write {}".format(html_hdfs_path))
            with hdfs_client.write(html_hdfs_path, overwrite=True) as writer:
                writer.write(response.html)
            
            process_html(url_path + ".html", response.userId)
                
            log_hdfs_path = hdfs_path + "/" + url_path + ".log"
            add_log(response.url, response.timestamp, log_hdfs_path)
                        

            print("Write {}".format(log_hdfs_path))
                        
            print(f"File saved to HDFS: {hdfs_path}")

    consumer.close()

process_all_html()
consume_and_save()