import os
import unittest
import utils
import time
import string
import json

IMAGE_NAME = 'confluentinc/cp-enterprise-control-center'
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(CURRENT_DIR, "fixtures", "debian", "control-center")
KAFKA_READY = "bash -c 'cub kafka-ready {brokers} 40 -z $KAFKA_ZOOKEEPER_CONNECT && echo PASS || echo FAIL'"
ZK_READY = "bash -c 'cub zk-ready {servers} 40 && echo PASS || echo FAIL'"
C3_CHECK = "bash -c 'dub wait {host} {port} 240 && curl -fs -X GET -i {host}:{port}/ && echo PASS || echo FAIL'"


def props_to_list(props_str):
    return sorted([
        p.strip() for p in props_str.split("\n") if len(p.strip()) > 0
    ])


class ConfigTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ['DOCKER_CLIENT_TIMEOUT'] = "600"
        machine_name = os.environ["DOCKER_MACHINE_NAME"]
        cls.machine = utils.TestMachine(machine_name)

        cls.cluster = utils.TestCluster("config-test", FIXTURES_DIR, "standalone-config.yml")
        cls.cluster.start()

        assert "PASS" in cls.cluster.run_command_on_service("zookeeper", ZK_READY.format(servers="localhost:2181"))
        assert "PASS" in cls.cluster.run_command_on_service("kafka", KAFKA_READY.format(brokers=1))

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()

    @classmethod
    def is_c3_healthy_for_service(cls, service):
        output = utils.run_docker_command(
            600,
            image=IMAGE_NAME,
            command=C3_CHECK.format(host=service, port=9021),
            host_config={'NetworkMode': 'config-test_default'}
        )
        assert "PASS" in output

    def test_required_config_failure(self):
        self.assertTrue("CONTROL_CENTER_BOOTSTRAP_SERVERS is required." in self.cluster.service_logs("failing-config", stopped=True))
        self.assertTrue("CONTROL_CENTER_ZOOKEEPER_CONNECT is required." in self.cluster.service_logs("failing-config-missing-zk-connect", stopped=True))
        self.assertTrue("CONTROL_CENTER_REPLICATION_FACTOR is required." in self.cluster.service_logs("failing-config-missing-rep-factor", stopped=True))

    def test_default_config(self):
        self.is_c3_healthy_for_service("default-config")
        props = props_to_list(self.cluster.run_command_on_service("default-config", "cat /etc/confluent-control-center/control-center.properties"))
        expected = props_to_list("""
        bootstrap.servers=kafka:9092
        zookeeper.connect=zookeeper:2181/defaultconfig
        confluent.monitoring.interceptor.topic.replication=1
        confluent.controlcenter.internal.topics.replication=1
        confluent.controlcenter.command.topic.replication=1
        confluent.metrics.topic.replication=1
        """)
        self.assertEquals(expected, props)

    def test_wildcards_config(self):
        output = self.cluster.run_command_on_service("wildcards-config", "bash -c 'while [ ! -f /tmp/config-is-done ]; do echo waiting && sleep 1; done; echo PASS'")
        assert "PASS" in output

        props = props_to_list(self.cluster.run_command_on_service("wildcards-config", "cat /etc/confluent-control-center/control-center.properties"))
        expected = props_to_list("""
        bootstrap.servers=kafka:9092
        zookeeper.connect=zookeeper:2181/defaultconfig
        confluent.monitoring.interceptor.topic.replication=1
        confluent.controlcenter.internal.topics.replication=1
        confluent.metrics.topic.replication=1
        confluent.controlcenter.command.topic.replication=3
        confluent.controlcenter.command.topic.retention.ms=1000
        confluent.controlcenter.connect.timeout=30000
        confluent.controlcenter.rest.listeners=http://0.0.0.0:9021,https://0.0.0.0:443
        confluent.controlcenter.streams.security.protocol=SOME_PROTOCOL
        confluent.controlcenter.streams.sasl.kerberos.service.name=kafka
        confluent.controlcenter.rest.ssl.keystore.location=/path/to/keystore
        confluent.controlcenter.mail.enabled=true
        confluent.controlcenter.mail.host.name=foo.com
        confluent.controlcenter.streams.producer.security.protocol=ANOTHER_PROTOCOL
        confluent.controlcenter.streams.producer.ssl.keystore.location=/path/to/keystore
        confluent.controlcenter.streams.producer.ssl.keystore.password=password
        confluent.controlcenter.streams.producer.ssl.key.password=password
        confluent.controlcenter.streams.producer.ssl.truststore.location=/path/to/truststore
        confluent.controlcenter.streams.producer.ssl.truststore.password=password
        confluent.controlcenter.streams.consumer.security.protocol=ANOTHER_PROTOCOL
        confluent.controlcenter.streams.consumer.ssl.keystore.location=/path/to/keystore
        confluent.controlcenter.streams.consumer.ssl.keystore.password=password
        confluent.controlcenter.streams.consumer.ssl.key.password=password
        confluent.controlcenter.streams.consumer.ssl.truststore.location=/path/to/truststore
        confluent.controlcenter.streams.consumer.ssl.truststore.password=password
        """)
        self.assertEquals(expected, props)

        admin_props = props_to_list(self.cluster.run_command_on_service("wildcards-config", "cat /etc/confluent-control-center/admin.properties"))
        admin_expected = props_to_list("""
        security.protocol=ANOTHER_PROTOCOL
        ssl.keystore.location=/path/to/keystore
        ssl.keystore.password=password
        ssl.key.password=password
        ssl.truststore.location=/path/to/truststore
        ssl.truststore.password=password
        """)
        self.assertEquals(admin_expected, admin_props)

    def test_admin_props_with_producer_overrides(self):
        output = self.cluster.run_command_on_service("security-config-with-producer-override",
                "bash -c 'while [ ! -f /tmp/config-is-done ]; do echo waiting && sleep 1; done; echo PASS'")
        assert "PASS" in output

        admin_props = props_to_list(self.cluster.run_command_on_service("security-config-with-producer-override",
            "cat /etc/confluent-control-center/admin.properties"))
        admin_expected = props_to_list("""
        security.protocol=SOME_PROTOCOL
        sasl.kerberos.service.name=kafka
        ssl.keystore.location=/path/to/keystore
        ssl.keystore.password=password
        ssl.key.password=password
        ssl.truststore.location=/path/to/truststore
        ssl.truststore.password=password
        linger.ms=1000
        """)
        self.assertEquals(admin_expected, admin_props)


class StandaloneNetworkingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cluster = utils.TestCluster("standalone-network-test", FIXTURES_DIR, "standalone-network.yml")
        cls.cluster.start()
        assert "PASS" in cls.cluster.run_command_on_service("zookeeper-bridge", ZK_READY.format(servers="localhost:2181"))
        assert "PASS" in cls.cluster.run_command_on_service("kafka-bridge", KAFKA_READY.format(brokers=1))

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()

    @classmethod
    def is_c3_healthy_for_service(cls, service, network):
        output = utils.run_docker_command(
            600,
            image=IMAGE_NAME,
            command=C3_CHECK.format(host=service, port=9021),
            host_config={'NetworkMode': network}
        )
        assert "PASS" in output

    def test_bridged_network(self):
        # Test from within the container
        self.is_c3_healthy_for_service("control-center-bridge", "standalone-network-test_zk")

        INTERCEPTOR_CLIENTS_CMD = """bash -xc '\
            export TOPIC="{topic}" \
            export MESSAGES="{messages}" \
            export CHECK_MESSAGES="{check_messages}"
            cub kafka-ready 1 40 -z "$ZOOKEEPER_CONNECT" \
            && control-center-run-class kafka.admin.TopicCommand --create --topic "$TOPIC" --partitions 1 --replication-factor 1 --zookeeper "$ZOOKEEPER_CONNECT" --if-not-exists \
            && seq "$MESSAGES" | control-center-run-class kafka.tools.ConsoleProducer --broker-list "$BOOTSTRAP_SERVERS" --topic "$TOPIC" --producer-property interceptor.classes=io.confluent.monitoring.clients.interceptor.MonitoringProducerInterceptor \
            && echo PRODUCED "$MESSAGES" messages. \
            && echo "interceptor.classes=io.confluent.monitoring.clients.interceptor.MonitoringConsumerInterceptor" > /tmp/consumer.config \
            && control-center-run-class kafka.tools.ConsoleConsumer --bootstrap-server "$BOOTSTRAP_SERVERS" --topic "$TOPIC" --new-consumer --from-beginning --max-messages "$CHECK_MESSAGES" --consumer.config /tmp/consumer.config'
            """

        MESSAGES = 10000
        TOPIC = 'test-topic'
        # Run producer and consumer with interceptor to generate monitoring data
        out = utils.run_docker_command(
            image=IMAGE_NAME,
            command=INTERCEPTOR_CLIENTS_CMD.format(topic=TOPIC, messages=MESSAGES, check_messages=MESSAGES),
            host_config={'NetworkMode': 'standalone-network-test_zk'},
            environment={'ZOOKEEPER_CONNECT': 'zookeeper-bridge:2181', 'BOOTSTRAP_SERVERS': 'kafka-bridge:19092'}
        )
        self.assertTrue("PRODUCED %s messages" % MESSAGES in out)

        # Check that data was processed
        # Calculate last hour and next hour in case we cross the border
        now_unix = int(time.time())
        prev_hr_start_unix = now_unix - now_unix % 3600
        next_hr_start_unix = prev_hr_start_unix + 2 * 3600

        # Fetch cluster id
        FETCH_CLUSTERS_CMD = """curl -s -H 'Content-Type: application/json' 'http://{host}:{port}/2.0/clusters/kafka/display/stream-monitoring'"""
        fetch_cluster_cmd_args = {
            'image': IMAGE_NAME,
            'command': FETCH_CLUSTERS_CMD.format(host="control-center-bridge", port=9021),
            'host_config': {'NetworkMode': 'standalone-network-test_zk'},
        }

        attempts = 0
        while attempts <= 60:
            attempts += 1
            out = json.loads(utils.run_docker_command(**fetch_cluster_cmd_args))
            self.assertTrue('defaultClusterId' in out)
            if out['defaultClusterId'] is None:
                time.sleep(5)
                continue
            else:
                self.assertTrue(len(out['clusters']) == 1, "Expected a single cluster in %s" % out)
                cluster_id = out['defaultClusterId']
                break

        # Fetch monitoring data
        FETCH_MONITORING_DATA_CMD = """curl -s -H 'Content-Type: application/json' 'http://{host}:{port}/2.0/monitoring/{cluster_id}/consumer_groups?startTimeMs={start}&stopTimeMs={stop}&rollup=ONE_HOUR'"""
        fetch_cmd_args = {
            'image': IMAGE_NAME,
            'command': FETCH_MONITORING_DATA_CMD.format(host="control-center-bridge", port=9021, start=prev_hr_start_unix * 1000, stop=next_hr_start_unix * 1000, cluster_id=cluster_id),
            'host_config': {'NetworkMode': 'standalone-network-test_zk'},
        }

        attempts = 0
        while attempts <= 60:
            attempts += 1
            out = json.loads(utils.run_docker_command(**fetch_cmd_args))
            self.assertTrue('sources' in out, 'Unexpected return data %s' % out)
            if len(out['sources']) == 0:
                time.sleep(5)
                continue
            else:
                self.assertEquals(1, len(out['sources']))
                self.assertEquals(TOPIC, out['sources'][0]['topic'])
                break
