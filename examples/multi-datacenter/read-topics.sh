#!/bin/bash

# This script is purely to output some interesting data to help you understand the replication process

echo -e "\n-----DC1-----"
echo -e "\nlist topics:"
docker-compose exec broker-dc1 kafka-topics --list --zookeeper zookeeper-dc1:2181
echo -e "\ntopic1:"
docker-compose exec schema-registry-dc1 kafka-avro-console-consumer --topic topic1 --bootstrap-server broker-dc1:9091 --property schema.registry.url=http://schema-registry-dc1:8081 --max-messages 10
echo -e "\n_schemas:"
docker-compose exec broker-dc1 kafka-console-consumer --topic _schemas --bootstrap-server broker-dc1:9091 --from-beginning --timeout-ms 5000
echo -e "\nprovenance info:"
docker-compose exec replicator-dc1-to-dc2 bash -c "export CLASSPATH=/usr/share/java/kafka-connect-replicator/kafka-connect-replicator-5.1.1.jar && kafka-console-consumer --topic topic1 --bootstrap-server broker-dc1:9091 --max-messages 10 --formatter=io.confluent.connect.replicator.tools.ProvenanceHeaderFormatter"
echo -e "\ncluster id:"
docker-compose exec zookeeper-dc1 zookeeper-shell localhost:2181 get /cluster/id | grep version | grep id | jq -r .id

echo -e "\n-----DC2-----"
echo -e "\nlist topics:"
docker-compose exec broker-dc2 kafka-topics --list --zookeeper zookeeper-dc2:2182
echo -e "\ntopic1:"
docker-compose exec schema-registry-dc1 kafka-avro-console-consumer --topic topic1 --bootstrap-server broker-dc2:9092 --property schema.registry.url=http://schema-registry-dc1:8081 --max-messages 10
echo -e "\n_schemas:"
docker-compose exec broker-dc1 kafka-console-consumer --topic _schemas --bootstrap-server broker-dc2:9092 --from-beginning --timeout-ms 5000
echo -e "\nprovenance info:"
docker-compose exec replicator-dc1-to-dc2 bash -c "export CLASSPATH=/usr/share/java/kafka-connect-replicator/kafka-connect-replicator-5.1.1.jar && kafka-console-consumer --topic topic1 --bootstrap-server broker-dc2:9092 --max-messages 10 --formatter=io.confluent.connect.replicator.tools.ProvenanceHeaderFormatter"
echo -e "\ncluster id:"
docker-compose exec zookeeper-dc2 zookeeper-shell localhost:2182 get /cluster/id | grep version | grep id | jq -r .id
