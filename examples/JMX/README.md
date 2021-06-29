# JMX Docker Compose example

In general, all Kafka services use the `*JMX_OPTS` environment variable to pass JMX options to the JVM. This compose example is configured to allow external JMX clients (e.g. jconsole) to connect to the containers' JMX port. 

If you log into the container you will see this environment variable being set. This can cause issues if you are running kafka CLI commands locally within the container. To work around this you *must* unset the `*JMX_OPTS` environment variable. For instance for the kafka container, you need to unset the `KAFKA_JMX_OPTS` before you can run any kafka CLI command:

```
root@14967682c840:/# unset KAFKA_JMX_OPTS
root@14967682c840:/# kafka-topics --zookeeper zookeeper:2181 --describe
```
