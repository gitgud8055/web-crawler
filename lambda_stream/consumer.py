from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, udf
from pyspark.sql.types import StructType, StringType, TimestampType
import uuid
from cassandra.cluster import Cluster

# Cassandra session 
cluster = Cluster(['localhost'], port=9042)
session = cluster.connect()

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
CREATE TABLE IF NOT EXISTS chatbot.conversations(
    id text,
    user_prompt text,
    model_response text,
    timestamp text,
    PRIMARY KEY (id)
   );
""").one()

# Write the data to Cassandra
def write_to_cassandra(batch_df, batch_id):
    batch_df.write \
        .format("org.apache.spark.sql.cassandra") \
        .options(table="conversations", keyspace="chatbot") \
        .mode("append") \
        .save()
            
# Initialize Spark Session
spark = SparkSession.builder \
    .appName("KafkaToCassandra") \
    .config("spark.cassandra.connection.host", "127.0.0.1:9042") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4,com.datastax.spark:spark-cassandra-connector_2.12:3.0.0") \
    .getOrCreate()


# Define the schema for incoming data
schema = StructType() \
    .add("user_prompt", StringType()) \
    .add("model_response", StringType()) \
    .add("timestamp", TimestampType())

# Read data from Kafka
kafka_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("subscribe", "chat-history") \
    .option("startingOffsets", "latest") \
    .load()

# Parse the Kafka messages
parsed_stream = kafka_stream.select(from_json(col("value").cast("string"), schema).alias("data")).select("data.*")

# Add a unique ID column
uuid_udf = udf(lambda: str(uuid.uuid4()), StringType())
processed_stream = parsed_stream.withColumn("id", uuid_udf())

query = processed_stream.writeStream \
    .foreachBatch(write_to_cassandra) \
    .outputMode("update") \
    .start()

query.awaitTermination()
    