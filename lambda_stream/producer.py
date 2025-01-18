from confluent_kafka import Producer
from uuid import uuid4
import json
import datetime

conf = {
    'bootstrap.servers': 'localhost:9092'
}
producer = Producer(conf)
topic = 'chat-history'
print("[Producer] Connected Kafka broker")

## KAFKA ## 
def delivery_report(err, msg):
    if err:
        print(f"Delivery failed for {msg.key()}: {err}")
    else:
        print('Delivery record {} successfully produced to {} [{}] at offset {}'.format(
            msg.key(), msg.topic(), msg.partition(), msg.offset()))

def publish_chat_event(user_input, model_response):
    send_msg = json.dumps({
        "user_prompt": user_input,
        "model_response": model_response,
        "timestamp": str(datetime.datetime.now())
    })
    try:
        producer.poll(0.0)
       
        producer.produce(topic=topic,
                key=str(uuid4()),
                value=send_msg,
                on_delivery=delivery_report)
    except ValueError:
        print("Invalid input, discarding record...")

    producer.flush()
    
if __name__ == "__main__":
    publish_chat_event("Hello", "Hi")