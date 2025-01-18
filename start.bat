@ECHO OFF

docker exec -it kafka kafka-topics --bootstrap-server 127.0.0.1:9092 --create --topic html --partitions 1 --replication-factor 1
docker exec -it kafka kafka-topics --bootstrap-server 127.0.0.1:9092 --create --topic chat-history --partitions 1 --replication-factor 1

REM Start background Python scripts
start python lambda_batch/consumer.py
set PYTHON_PID_1=%ERRORLEVEL%

REM Start Spark job in the background
start /B spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4,com.datastax.spark:spark-cassandra-connector_2.12:3.0.0 lambda_stream/consumer.py
set SPARK_PID=%ERRORLEVEL%

REM Start foreground Python script
start /B python gr_bot.py
set PYTHON_PID_2=%ERRORLEVEL%

REM Wait for foreground script to finish
waitfor /t 60 gr_bot_done

REM If any process fails, terminate the background processes
if %ERRORLEVEL% neq 0 (
    taskkill /F /PID %PYTHON_PID_1% >nul 2>&1
    taskkill /F /PID %SPARK_PID% >nul 2>&1
    taskkill /F /PID %PYTHON_PID_2% >nul 2>&1
)

exit /B

:gr_bot_done