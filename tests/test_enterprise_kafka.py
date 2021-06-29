import os
import unittest
import utils
import time
import string
import json

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(CURRENT_DIR, "fixtures", "debian", "enterprise-kafka")
HEALTH_CHECK = """bash -c 'cp /etc/kafka/kafka.properties /tmp/cub.properties \
                  && echo security.protocol={security_protocol} >> /tmp/cub.properties \
                  && echo "metric.reporters=" >> /tmp/cub.properties \
                  && cub kafka-ready {brokers} 40 -b {host}:{port} -c /tmp/cub.properties -s {security_protocol}\
                  && echo PASS || echo FAIL'
                """
ZK_READY = "bash -c 'cub zk-ready {servers} 40 && echo PASS || echo FAIL'"
KAFKA_CHECK = "bash -c 'kafkacat -L -b {host}:{port} -J' "
TOPIC_EXISTS_CHECK = "bash -c 'kafka-topics --list --zookeeper $KAFKA_ZOOKEEPER_CONNECT | grep {topic} && echo PASS || echo FAIL'"
ADB_PROPOSED_ASSIGNMENT = "bash -c 'confluent-rebalancer proposed-assignment --zookeeper $KAFKA_ZOOKEEPER_CONNECT --metrics-bootstrap-server {brokers}'"
ADB_EXECUTE = "bash -c 'confluent-rebalancer execute --zookeeper $KAFKA_ZOOKEEPER_CONNECT --metrics-bootstrap-server {brokers} --throttle {throttle_bps} --remove-broker-ids {remove_broker} --force --verbose'"
ADB_FINISH = "bash -c 'confluent-rebalancer finish --zookeeper $KAFKA_ZOOKEEPER_CONNECT'"
ADB_STATUS = "bash -c 'confluent-rebalancer status --zookeeper $KAFKA_ZOOKEEPER_CONNECT'"
GENERATE_PERF_DATA = "bash -c 'kafka-producer-perf-test --topic {topic} --num-records {record_count} --record-size {record_size_bytes} --throughput {throughput_rps} --producer-props bootstrap.servers={brokers}'"
TOPIC_CREATE = "bash -c 'kafka-topics --create --topic {topic} --partitions {partitions} --replication-factor {replicas} --if-not-exists --zookeeper $KAFKA_ZOOKEEPER_CONNECT'"


class ConfigTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        machine_name = os.environ["DOCKER_MACHINE_NAME"]
        cls.machine = utils.TestMachine(machine_name)

        cls.cluster = utils.TestCluster("config-test", FIXTURES_DIR, "standalone-config.yml")
        cls.cluster.start()

        assert "PASS" in cls.cluster.run_command_on_service("zookeeper", ZK_READY.format(servers="localhost:2181"))

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()

    @classmethod
    def is_kafka_healthy_for_service(cls, service, port, num_brokers, host="localhost", security_protocol="PLAINTEXT"):
        output = cls.cluster.run_command_on_service(service, HEALTH_CHECK.format(host=host, port=port, brokers=num_brokers, security_protocol=security_protocol))
        assert "PASS" in output

    def test_adb_config(self):
        self.is_kafka_healthy_for_service("adb-metrics", 9092, 1)
        zk_props = self.cluster.run_command_on_service("adb-metrics", "bash -c 'cat /etc/kafka/kafka.properties | sort'")
        expected = """
                advertised.listeners=PLAINTEXT://adb-metrics:9092
                broker.id=1
                confluent.metrics.reporter.bootstrap.servers=adb-metrics:9092
                confluent.metrics.reporter.topic.replicas=1
                confluent.metrics.reporter.zookeeper.connect=zookeeper:2181/adb-metrics
                confluent.support.customer.id=c0
                confluent.support.metrics.enable=false
                listeners=PLAINTEXT://0.0.0.0:9092
                log.dirs=/var/lib/kafka/data
                metric.reporters=io.confluent.metrics.reporter.ConfluentMetricsReporter
                zookeeper.connect=zookeeper:2181/adb-metrics
                """
        self.assertEquals(zk_props.translate(None, string.whitespace), expected.translate(None, string.whitespace))
        for i in xrange(20):
          if ("PASS" in  self.cluster.run_command_on_service("adb-metrics", TOPIC_EXISTS_CHECK.format(topic="_confluent-metrics"))):
            break
          time.sleep(1)

        self.assertTrue("PASS" in self.cluster.run_command_on_service("adb-metrics", TOPIC_EXISTS_CHECK.format(topic="_confluent-metrics")))


class ClusterHostNetworkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cluster = utils.TestCluster("cluster-test", FIXTURES_DIR, "cluster-host-plain.yml")
        cls.cluster.start()
        assert "PASS" in cls.cluster.run_command_on_service("zookeeper-1", ZK_READY.format(servers="localhost:22181,localhost:32181,localhost:42181"))

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()

    def test_cluster_running(self):
        self.assertTrue(self.cluster.is_running())

    @classmethod
    def is_kafka_healthy_for_service(cls, service, port, num_brokers, host="localhost", security_protocol="PLAINTEXT"):
        output = cls.cluster.run_command_on_service(service, HEALTH_CHECK.format(host=host, port=port, brokers=num_brokers, security_protocol=security_protocol))
        assert "PASS" in output

    def test_adb(self):
        self.is_kafka_healthy_for_service("kafka-1", 19092, 3)
        topic = "test-adb-metrics"
        topic_output = self.cluster.run_command_on_service("kafka-1", TOPIC_CREATE.format(topic=topic, partitions=10, replicas=3))
        assert 'Created topic "%s".' % topic in topic_output

        record_count = 100000
        produce_data_output = self.cluster.run_command_on_service("kafka-1", GENERATE_PERF_DATA.format(brokers="localhost:19092", topic=topic, record_count=record_count, record_size_bytes=1000, throughput_rps=100000))
        assert "%s records sent" % record_count in produce_data_output

        proposed_assignment_output = self.cluster.run_command_on_service("kafka-1", ADB_PROPOSED_ASSIGNMENT.format(brokers="localhost:19092"))
        assert "version" in proposed_assignment_output

        removed_broker = 1
        execute_logs = utils.run_docker_command(
            300,  # Timeout = 5 mins
            image="confluentinc/cp-enterprise-kafka",
            name="adb-execute",
            environment={'KAFKA_ZOOKEEPER_CONNECT': "localhost:22181,localhost:32181,localhost:42181"},
            command=ADB_EXECUTE.format(brokers="localhost:19092", throttle_bps=100000000, remove_broker=removed_broker),
            host_config={'NetworkMode': 'host'})

        assert "Computing the rebalance plan (this may take a while)" in execute_logs

        rebalance_status = self.cluster.run_command_on_service("kafka-1", ADB_STATUS)

        rebalance_complete = ""
        for i in xrange(120):
            rebalance_complete = self.cluster.run_command_on_service("kafka-1", ADB_FINISH)
            if "The rebalance has completed and throttling has been disabled" in rebalance_complete:
                break
            time.sleep(1)

        assert "The rebalance has completed and throttling has been disabled" in rebalance_complete

        rebalance_status = self.cluster.run_command_on_service("kafka-1", ADB_STATUS)
        assert "No rebalance is currently in progress" in rebalance_status

        # Verify that the removed broker has no partitions
        logs = utils.run_docker_command(
            image="confluentinc/cp-kafkacat",
            command=KAFKA_CHECK.format(host="localhost", port=19092),
            host_config={'NetworkMode': 'host'})

        parsed_logs = json.loads(logs)
        topics = parsed_logs["topics"]
        for t in parsed_logs["topics"]:
            for p in t["partitions"]:
                for r in p["replicas"]:
                    assert r["id"] != removed_broker
