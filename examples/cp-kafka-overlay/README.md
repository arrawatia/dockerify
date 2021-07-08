# RADAR-CNS with multi-node cluster using Docker Swarm 


# If you require attachable networks for testing, you'll need to create them as external e.g.
```sh
docker network create --attachable --driver overlay zookeeper
docker network create --attachable --driver overlay kafka
docker network create --attachable --driver overlay api
```


# Run the full setup with (NB! --compose-file only works with Docker v1.13.x)
```sh
docker deploy --compose-file docker-compose.yml kafka-overlay
```



#Test
```sh
docker run --net=zookeeper --rm confluentinc/cp-zookeeper:3.1.1 bash -c "echo stat | nc zookeeper-1 2181 | grep Mode"
```
> Mode: standalone

```sh
docker run --net=kafka --rm confluentinc/cp-kafka:3.1.1 kafka-topics --create --topic foo --partitions 1 --replication-factor 1 --if-not-exists --zookeeper zookeeper-1:2181
```
> Created topic "foo".


```sh
docker run --net=kafka --rm confluentinc/cp-kafka:3.1.1 kafka-topics --describe --topic foo --zookeeper zookeeper-1:2181
```
> Topic:foo   PartitionCount:1    ReplicationFactor:1 Configs:
>    Topic: foo  Partition: 0    Leader: 3   Replicas: 3 Isr: 3


