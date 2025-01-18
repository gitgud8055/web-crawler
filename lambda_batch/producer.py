import asyncio
import aiohttp
from uuid import uuid4
from confluent_kafka import Producer
import json
from lambda_batch.__init__ import Response

# Assuming you have a running Kafka server at localhost:9092
conf = {
    'bootstrap.servers': 'localhost:9092',
    'message.max.bytes': 5242880
}
producer = Producer(conf)
topic = 'html'
print("Connect Kafka!")

# class Response:
#     url: str
#     timestamp: str
#     html: str
#     userId: str
        
#     def __init__(self, response):
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

async def fetch(payload):
    endpoint = "http://localhost:2000/fetch-html"
    headers = {'Content-Type': 'application/json'}
    
    async with aiohttp.ClientSession(read_bufsize=1024 * 1024) as session:  # Increase buffer size
        async with session.post(endpoint, headers=headers, json=payload) as response:
            if response.status == 200:
                async for line in response.content:
                    yield json.loads(line.decode("utf-8"))
            else:
                raise RuntimeError(f"Failed to receive stream: {response.status}")



def delivery_report(err, msg):
    if err:
        print(f"Delivery failed for {msg.key()}: {err}")
    else:
        print('Delivery record {} successfully produced to {} [{}] at offset {}'.format(
            msg.key(), msg.topic(), msg.partition(), msg.offset()))

async def produce(urls, depth=1, userId=""):
    for url in urls:
        payload = {
            "url": url,
            "depth": depth,
        }
        
        async for response_raw in fetch(payload):
            try:
                producer.poll(0.1)  # Keeps Kafka producer alive
                
                # Convert response_raw to your desired format (e.g., `Response` class)
                response_raw["userId"] = userId
                response = Response(response=response_raw)
                print(f"URL: {response.url} - {response.timestamp}")
                
                import sys
                print(f"Message size: {sys.getsizeof(response.json)} bytes")

                producer.produce(topic=topic,
                                 key=str(uuid4()),
                                 value=response.json,
                                 on_delivery=delivery_report)
            except ValueError:
                print("Invalid input, discarding record...")
                continue

    producer.flush()

# async def run_produce_async(urls, depth=1):
#     await produce(urls, depth)

async def run_produce_async(*args, **kwargs):
    await produce(*args, **kwargs)

if __name__ == "__main__":
    urls = ["https://en.wikipedia.org/wiki/Vladimir_Lenin"]
    depth = 1
    asyncio.run(run_produce_async(urls, depth))
    print("Producer has finished processing.")
