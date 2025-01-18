#!/bin/bash

# Function to terminate processes if any fail
terminate_processes() {
    kill -9 $PYTHON_PID_1 $SPARK_PID $PYTHON_PID_2 2>/dev/null
}

# Start background Python scripts
python lambda_batch/consumer.py &
PYTHON_PID_1=$!

# Start Spark job in the background
spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4,com.datastax.spark:spark-cassandra-connector_2.12:3.0.0 lambda_stream/consumer.py &
SPARK_PID=$!

# Start foreground Python script
python gr_bot.py &
PYTHON_PID_2=$!

# Wait for the foreground script to finish or timeout after 60 seconds
timeout 60s wait $PYTHON_PID_2

# If the foreground script finishes with an error, terminate the background processes
if [ $? -ne 0 ]; then
    terminate_processes
fi

exit 0
