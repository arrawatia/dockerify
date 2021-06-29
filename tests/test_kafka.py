import os
import unittest
import utils
import time
import string
import json

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(CURRENT_DIR, "fixtures", "debian", "kafka")
HEALTH_CHECK = """bash -c 'cp /etc/kafka/kafka.properties /tmp/cub.properties \
                  && echo security.protocol={security_protocol} >> /tmp/cub.properties \
                  && cub kafka-ready {brokers} 40 -b {host}:{port} -c /tmp/cub.properties -s {security_protocol}\
                  && echo PASS || echo FAIL'
                """
ZK_READY = "bash -c 'cub zk-ready {servers} 40 && echo PASS || echo FAIL'"
KAFKA_CHECK = "bash -c 'kafkacat -L -b {host}:{port} -J' "
KAFKA_SASL_SSL_CHECK = """bash -c "kafkacat -X 'security.protocol=sasl_ssl' \
      -X 'ssl.ca.location=/etc/kafka/secrets/snakeoil-ca-1.crt' \
      -X 'ssl.certificate.location=/etc/kafka/secrets/kafkacat-ca1-signed.pem' \
      -X 'ssl.key.location=/etc/kafka/secrets/kafkacat.client.key' \
      -X 'ssl.key.password=confluent' \
      -X 'sasl.kerberos.service.name={broker_principal}' \
      -X 'sasl.kerberos.keytab=/etc/kafka/secrets/{client_principal}.keytab' \
      -X 'sasl.kerberos.principal={client_principal}/{client_host}' \
      -L -b {host}:{port} -J "
      """

KAFKA_SSL_CHECK = """kafkacat -X security.protocol=ssl \
      -X ssl.ca.location=/etc/kafka/secrets/snakeoil-ca-1.crt \
      -X ssl.certificate.location=/etc/kafka/secrets/kafkacat-ca1-signed.pem \
      -X ssl.key.location=/etc/kafka/secrets/kafkacat.client.key \
      -X ssl.key.password=confluent \
      -L -b {host}:{port} -J"""

KADMIN_KEYTAB_CREATE = """bash -c \
        'kadmin.local -q "addprinc -randkey {principal}/{hostname}@TEST.CONFLUENT.IO" && \
        kadmin.local -q "ktadd -norandkey -k /tmp/keytab/{filename}.keytab {principal}/{hostname}@TEST.CONFLUENT.IO"'
        """

PRODUCER = """bash -c "\
    kafka-topics --create --topic {topic} --partitions 1 --replication-factor 3 --if-not-exists --zookeeper $KAFKA_ZOOKEEPER_CONNECT \
    && seq {messages} | kafka-console-producer --broker-list {brokers} --topic {topic} --producer.config /etc/kafka/secrets/{config} \
    && seq {messages} | kafka-console-producer --broker-list {brokers} --topic {topic} --producer.config /etc/kafka/secrets/{config} \
    && echo PRODUCED {messages} messages."
    """

CONSUMER = """bash -c "\
        export KAFKA_TOOLS_LOG4J_LOGLEVEL=DEBUG \
        && dub template "/etc/confluent/docker/tools-log4j.properties.template" "/etc/kafka/tools-log4j.properties" \
        && kafka-console-consumer --bootstrap-server {brokers} --topic foo --new-consumer --from-beginning --consumer.config /etc/kafka/secrets/{config} --max-messages {messages}"
        """

KAFKACAT_SSL_CONSUMER = """kafkacat -X security.protocol=ssl \
      -X ssl.ca.location=/etc/kafka/secrets/snakeoil-ca-1.crt \
      -X ssl.certificate.location=/etc/kafka/secrets/kafkacat-ca1-signed.pem \
      -X ssl.key.location=/etc/kafka/secrets/kafkacat.client.key \
      -X ssl.key.password=confluent \
      -b {brokers} \
      -C -t {topic} -c {messages}
    """

PLAIN_CLIENTS = """bash -c "\
    export KAFKA_TOOLS_LOG4J_LOGLEVEL=DEBUG \
    && dub template /etc/confluent/docker/tools-log4j.properties.template /etc/kafka/tools-log4j.properties \
    && kafka-topics --create --topic {topic} --partitions 1 --replication-factor 3 --if-not-exists --zookeeper $KAFKA_ZOOKEEPER_CONNECT \
    && seq {messages} | kafka-console-producer --broker-list {brokers} --topic {topic} \
    && echo PRODUCED {messages} messages. \
    && kafka-console-consumer --bootstrap-server {brokers} --topic foo --new-consumer --from-beginning --max-messages {messages}"
    """

JMX_CHECK = """bash -c "\
    echo 'get -b kafka.server:id=1,type=app-info Version' |
        java -jar jmxterm-1.0-alpha-4-uber.jar -l {jmx_hostname}:{jmx_port} -n -v silent "
"""


class ConfigTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        machine_name = os.environ["DOCKER_MACHINE_NAME"]
        cls.machine = utils.TestMachine(machine_name)

        # Create directories with the correct permissions for test with userid and external volumes.
        cls.machine.ssh("mkdir -p /tmp/kafka-config-kitchen-sink-test/data")
        cls.machine.ssh("sudo chown -R 12345 /tmp/kafka-config-kitchen-sink-test/data")

        # Copy SSL files.
        cls.machine.ssh("mkdir -p /tmp/kafka-config-test/secrets")
        local_secrets_dir = os.path.join(FIXTURES_DIR, "secrets")
        cls.machine.scp_to_machine(local_secrets_dir, "/tmp/kafka-config-test")

        cls.cluster = utils.TestCluster("config-test", FIXTURES_DIR, "standalone-config.yml")
        cls.cluster.start()

        # Create keytabs
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="broker1", principal="kafka", hostname="sasl-ssl-config"))

        assert "PASS" in cls.cluster.run_command_on_service("zookeeper", ZK_READY.format(servers="localhost:2181"))

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()
        cls.machine.ssh("sudo rm -rf /tmp/kafka-config-kitchen-sink-test")
        cls.machine.ssh("sudo rm -rf /tmp/kafka-config-test/secrets")

    @classmethod
    def is_kafka_healthy_for_service(cls, service, port, num_brokers, host="localhost", security_protocol="PLAINTEXT"):
        output = cls.cluster.run_command_on_service(service, HEALTH_CHECK.format(host=host, port=port, brokers=num_brokers, security_protocol=security_protocol))
        assert "PASS" in output

    def test_required_config_failure(self):
        self.assertTrue("KAFKA_ZOOKEEPER_CONNECT is required." in self.cluster.service_logs("failing-config-zk-connect", stopped=True))
        self.assertTrue("KAFKA_ADVERTISED_LISTENERS is required." in self.cluster.service_logs("failing-config-adv-listeners", stopped=True))
        # Deprecated props.
        self.assertTrue("advertised.host is deprecated. Please use KAFKA_ADVERTISED_LISTENERS instead." in self.cluster.service_logs("failing-config-adv-hostname", stopped=True))
        self.assertTrue("advertised.port is deprecated. Please use KAFKA_ADVERTISED_LISTENERS instead." in self.cluster.service_logs("failing-config-adv-port", stopped=True))
        self.assertTrue("port is deprecated. Please use KAFKA_ADVERTISED_LISTENERS instead." in self.cluster.service_logs("failing-config-port", stopped=True))
        self.assertTrue("host is deprecated. Please use KAFKA_ADVERTISED_LISTENERS instead." in self.cluster.service_logs("failing-config-host", stopped=True))
        # SSL
        self.assertTrue("KAFKA_SSL_KEYSTORE_FILENAME is required." in self.cluster.service_logs("failing-config-ssl-keystore", stopped=True))
        self.assertTrue("KAFKA_SSL_KEYSTORE_CREDENTIALS is required." in self.cluster.service_logs("failing-config-ssl-keystore-password", stopped=True))
        self.assertTrue("KAFKA_SSL_KEY_CREDENTIALS is required." in self.cluster.service_logs("failing-config-ssl-key-password", stopped=True))
        self.assertTrue("KAFKA_SSL_TRUSTSTORE_FILENAME is required." in self.cluster.service_logs("failing-config-ssl-truststore", stopped=True))
        self.assertTrue("KAFKA_SSL_TRUSTSTORE_CREDENTIALS is required." in self.cluster.service_logs("failing-config-ssl-truststore-password", stopped=True))

        self.assertTrue("KAFKA_OPTS is required." in self.cluster.service_logs("failing-config-sasl-jaas", stopped=True))
        self.assertTrue("KAFKA_OPTS should contain 'java.security.auth.login.config' property." in self.cluster.service_logs("failing-config-sasl-missing-prop", stopped=True))

    def test_default_config(self):
        self.is_kafka_healthy_for_service("default-config", 9092, 1)
        props = self.cluster.run_command_on_service("default-config", "bash -c 'cat /etc/kafka/kafka.properties | sort'")
        expected = """
            advertised.listeners=PLAINTEXT://default-config:9092
            listeners=PLAINTEXT://0.0.0.0:9092
            log.dirs=/var/lib/kafka/data
            zookeeper.connect=zookeeper:2181/defaultconfig
            """
        self.assertEquals(props.translate(None, string.whitespace), expected.translate(None, string.whitespace))

        logs = utils.run_docker_command(
            image="confluentinc/cp-kafkacat",
            command=KAFKA_CHECK.format(host="default-config", port=9092),
            host_config={'NetworkMode': 'config-test_default'})

        parsed_logs = json.loads(logs)
        expected_brokers = [{"id": 1001, "name": "default-config:9092"}]
        self.assertEquals(sorted(expected_brokers), sorted(parsed_logs["brokers"]))

    def test_default_logging_config(self):
        self.is_kafka_healthy_for_service("default-config", 9092, 1)

        log4j_props = self.cluster.run_command_on_service("default-config", "cat /etc/kafka/log4j.properties")
        expected_log4j_props = """log4j.rootLogger=INFO, stdout

            log4j.appender.stdout=org.apache.log4j.ConsoleAppender
            log4j.appender.stdout.layout=org.apache.log4j.PatternLayout
            log4j.appender.stdout.layout.ConversionPattern=[%d] %p %m (%c)%n


            log4j.logger.kafka.authorizer.logger=WARN
            log4j.logger.kafka.log.LogCleaner=INFO
            log4j.logger.kafka.producer.async.DefaultEventHandler=DEBUG
            log4j.logger.kafka.controller=TRACE
            log4j.logger.kafka.network.RequestChannel$=WARN
            log4j.logger.kafka.request.logger=WARN
            log4j.logger.state.change.logger=TRACE
            log4j.logger.kafka=INFO
            """
        self.assertEquals(log4j_props.translate(None, string.whitespace), expected_log4j_props.translate(None, string.whitespace))

        tools_log4j_props = self.cluster.run_command_on_service("default-config", "cat /etc/kafka/tools-log4j.properties")
        expected_tools_log4j_props = """log4j.rootLogger=WARN, stderr

            log4j.appender.stderr=org.apache.log4j.ConsoleAppender
            log4j.appender.stderr.layout=org.apache.log4j.PatternLayout
            log4j.appender.stderr.layout.ConversionPattern=[%d] %p %m (%c)%n
            log4j.appender.stderr.Target=System.err
            """
        self.assertEquals(tools_log4j_props.translate(None, string.whitespace), expected_tools_log4j_props.translate(None, string.whitespace))

    def test_full_config(self):
        self.is_kafka_healthy_for_service("full-config", 9092, 1)
        props = self.cluster.run_command_on_service("full-config", "bash -c 'cat /etc/kafka/kafka.properties | sort'")
        expected = """
                advertised.listeners=PLAINTEXT://full-config:9092
                broker.id=1
                listeners=PLAINTEXT://0.0.0.0:9092
                log.dirs=/var/lib/kafka/data
                zookeeper.connect=zookeeper:2181/fullconfig
                """
        self.assertEquals(props.translate(None, string.whitespace), expected.translate(None, string.whitespace))

    def test_full_logging_config(self):
        self.is_kafka_healthy_for_service("full-config", 9092, 1)

        log4j_props = self.cluster.run_command_on_service("full-config", "cat /etc/kafka/log4j.properties")
        expected_log4j_props = """log4j.rootLogger=WARN, stdout

            log4j.appender.stdout=org.apache.log4j.ConsoleAppender
            log4j.appender.stdout.layout=org.apache.log4j.PatternLayout
            log4j.appender.stdout.layout.ConversionPattern=[%d] %p %m (%c)%n


            log4j.logger.kafka.authorizer.logger=WARN
            log4j.logger.kafka.log.LogCleaner=INFO
            log4j.logger.kafka.producer.async.DefaultEventHandler=DEBUG
            log4j.logger.kafka.controller=WARN
            log4j.logger.kafka.network.RequestChannel$=WARN
            log4j.logger.kafka.request.logger=WARN
            log4j.logger.state.change.logger=TRACE
            log4j.logger.kafka.foo.bar=DEBUG
            log4j.logger.kafka=INFO
            """
        self.assertEquals(log4j_props.translate(None, string.whitespace), expected_log4j_props.translate(None, string.whitespace))

        tools_log4j_props = self.cluster.run_command_on_service("full-config", "cat /etc/kafka/tools-log4j.properties")
        expected_tools_log4j_props = """log4j.rootLogger=ERROR, stderr

            log4j.appender.stderr=org.apache.log4j.ConsoleAppender
            log4j.appender.stderr.layout=org.apache.log4j.PatternLayout
            log4j.appender.stderr.layout.ConversionPattern=[%d] %p %m (%c)%n
            log4j.appender.stderr.Target=System.err
            """
        self.assertEquals(tools_log4j_props.translate(None, string.whitespace), expected_tools_log4j_props.translate(None, string.whitespace))

    def test_volumes(self):
        self.is_kafka_healthy_for_service("external-volumes", 9092, 1)

    def test_random_user(self):
        self.is_kafka_healthy_for_service("random-user", 9092, 1)

    def test_kitchen_sink(self):
        self.is_kafka_healthy_for_service("kitchen-sink", 9092, 1)
        zk_props = self.cluster.run_command_on_service("kitchen-sink", "bash -c 'cat /etc/kafka/kafka.properties | sort'")
        expected = """
                advertised.listeners=PLAINTEXT://kitchen-sink:9092
                broker.id=1
                confluent.support.customer.id=c0
                confluent.support.metrics.enable=false
                listeners=PLAINTEXT://0.0.0.0:9092
                log.dirs=/var/lib/kafka/data
                zookeeper.connect=zookeeper:2181/kitchensink
                """
        self.assertEquals(zk_props.translate(None, string.whitespace), expected.translate(None, string.whitespace))

    def test_ssl_config(self):
        self.is_kafka_healthy_for_service("ssl-config", 9092, 1, "ssl-config", "SSL")
        zk_props = self.cluster.run_command_on_service("ssl-config", "bash -c 'cat /etc/kafka/kafka.properties | sort'")
        expected = """
                advertised.listeners=SSL://ssl-config:9092
                broker.id=1
                listeners=SSL://0.0.0.0:9092
                log.dirs=/var/lib/kafka/data
                security.inter.broker.protocol=SSL
                ssl.key.credentials=broker1_sslkey_creds
                ssl.key.password=confluent
                ssl.keystore.credentials=broker1_keystore_creds
                ssl.keystore.filename=kafka.broker1.keystore.jks
                ssl.keystore.location=/etc/kafka/secrets/kafka.broker1.keystore.jks
                ssl.keystore.password=confluent
                ssl.truststore.credentials=broker1_truststore_creds
                ssl.truststore.filename=kafka.broker1.truststore.jks
                ssl.truststore.location=/etc/kafka/secrets/kafka.broker1.truststore.jks
                ssl.truststore.password=confluent
                zookeeper.connect=zookeeper:2181/sslconfig
                """
        self.assertEquals(zk_props.translate(None, string.whitespace), expected.translate(None, string.whitespace))

    def test_sasl_config(self):
        self.is_kafka_healthy_for_service("sasl-ssl-config", 9094, 1, "sasl-ssl-config", "SASL_SSL")
        zk_props = self.cluster.run_command_on_service("sasl-ssl-config", "bash -c 'cat /etc/kafka/kafka.properties | sort'")
        expected = """
                advertised.listeners=SSL://sasl-ssl-config:9092,SASL_SSL://sasl-ssl-config:9094
                broker.id=1
                listeners=SSL://0.0.0.0:9092,SASL_SSL://0.0.0.0:9094
                log.dirs=/var/lib/kafka/data
                sasl.enabled.mechanisms=GSSAPI
                sasl.kerberos.service.name=kafka
                sasl.mechanism.inter.broker.protocol=GSSAPI
                security.inter.broker.protocol=SASL_SSL
                ssl.key.credentials=broker1_sslkey_creds
                ssl.key.password=confluent
                ssl.keystore.credentials=broker1_keystore_creds
                ssl.keystore.filename=kafka.broker1.keystore.jks
                ssl.keystore.location=/etc/kafka/secrets/kafka.broker1.keystore.jks
                ssl.keystore.password=confluent
                ssl.truststore.credentials=broker1_truststore_creds
                ssl.truststore.filename=kafka.broker1.truststore.jks
                ssl.truststore.location=/etc/kafka/secrets/kafka.broker1.truststore.jks
                ssl.truststore.password=confluent
                zookeeper.connect=zookeeper:2181/sslsaslconfig
                """
        self.assertEquals(zk_props.translate(None, string.whitespace), expected.translate(None, string.whitespace))


class StandaloneNetworkingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cluster = utils.TestCluster("standalone-network-test", FIXTURES_DIR, "standalone-network.yml")
        cls.cluster.start()
        assert "PASS" in cls.cluster.run_command_on_service("zookeeper-bridge", ZK_READY.format(servers="localhost:2181"))
        assert "PASS" in cls.cluster.run_command_on_service("zookeeper-host", ZK_READY.format(servers="localhost:32181"))

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()

    @classmethod
    def is_kafka_healthy_for_service(cls, service, port, num_brokers, host="localhost", security_protocol="PLAINTEXT"):
        output = cls.cluster.run_command_on_service(service, HEALTH_CHECK.format(host=host, port=port, brokers=num_brokers, security_protocol=security_protocol))
        assert "PASS" in output

    def test_bridged_network(self):
        # Test from within the container
        self.is_kafka_healthy_for_service("kafka-bridge", 19092, 1)
        # Test from outside the container
        logs = utils.run_docker_command(
            image="confluentinc/cp-kafkacat",
            command=KAFKA_CHECK.format(host="localhost", port=19092),
            host_config={'NetworkMode': 'host'})

        parsed_logs = json.loads(logs)
        self.assertEquals(1, len(parsed_logs["brokers"]))
        self.assertEquals(1, parsed_logs["brokers"][0]["id"])
        self.assertEquals("localhost:19092", parsed_logs["brokers"][0]["name"])

    def test_host_network(self):
        # Test from within the container
        self.is_kafka_healthy_for_service("kafka-host", 29092, 1)
        # Test from outside the container
        logs = utils.run_docker_command(
            image="confluentinc/cp-kafkacat",
            command=KAFKA_CHECK.format(host="localhost", port=29092),
            host_config={'NetworkMode': 'host'})

        parsed_logs = json.loads(logs)
        self.assertEquals(1, len(parsed_logs["brokers"]))
        self.assertEquals(1, parsed_logs["brokers"][0]["id"])
        self.assertEquals("localhost:29092", parsed_logs["brokers"][0]["name"])

    def test_jmx_host_network(self):

        # Test from outside the container
        logs = utils.run_docker_command(
            image="confluentinc/cp-jmxterm",
            command=JMX_CHECK.format(jmx_hostname="localhost", jmx_port="39999"),
            host_config={'NetworkMode': 'host'})
        self.assertTrue("Version = 0.11.0.1-cp1;" in logs)

    def test_jmx_bridged_network(self):

        # Test from outside the container
        logs = utils.run_docker_command(
            image="confluentinc/cp-jmxterm",
            command=JMX_CHECK.format(jmx_hostname="kafka-bridged-jmx", jmx_port="9999"),
            host_config={'NetworkMode': 'standalone-network-test_zk'})
        self.assertTrue("Version = 0.11.0.1-cp1;" in logs)


class ClusterBridgedNetworkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cluster = utils.TestCluster("cluster-test", FIXTURES_DIR, "cluster-bridged-plain.yml")
        cls.cluster.start()
        assert "PASS" in cls.cluster.run_command_on_service("zookeeper-1", ZK_READY.format(servers="zookeeper-1:2181,zookeeper-2:2181,zookeeper-3:2181"))

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()

    def test_cluster_running(self):
        self.assertTrue(self.cluster.is_running())

    @classmethod
    def is_kafka_healthy_for_service(cls, service, port, num_brokers, host="localhost", security_protocol="PLAINTEXT"):
        output = cls.cluster.run_command_on_service(service, HEALTH_CHECK.format(host=host, port=port, brokers=num_brokers, security_protocol=security_protocol))
        assert "PASS" in output

    def test_bridge_network(self):
        # Test from within the container
        self.is_kafka_healthy_for_service("kafka-1", 9092, 3)
        # Test from outside the container
        logs = utils.run_docker_command(
            image="confluentinc/cp-kafkacat",
            command=KAFKA_CHECK.format(host="kafka-1", port=9092),
            host_config={'NetworkMode': 'cluster-test_zk'})

        parsed_logs = json.loads(logs)
        self.assertEquals(3, len(parsed_logs["brokers"]))
        expected_brokers = [{"id": 1, "name": "kafka-1:9092"}, {"id": 2, "name": "kafka-2:9092"}, {"id": 3, "name": "kafka-3:9092"}]
        self.assertEquals(sorted(expected_brokers), sorted(parsed_logs["brokers"]))

        client_logs = utils.run_docker_command(
            300,
            image="confluentinc/cp-kafka",
            name="kafka-producer",
            environment={'KAFKA_ZOOKEEPER_CONNECT': "zookeeper-1:2181,zookeeper-2:2181,zookeeper-3:2181"},
            command=PLAIN_CLIENTS.format(brokers="kafka-1:9092", topic="foo", messages=100),
            host_config={'NetworkMode': 'cluster-test_zk'})

        self.assertTrue("Processed a total of 100 messages" in client_logs)


class ClusterSSLBridgedNetworkTest(ClusterBridgedNetworkTest):
    @classmethod
    def setUpClass(cls):
        machine_name = os.environ["DOCKER_MACHINE_NAME"]
        cls.machine = utils.TestMachine(machine_name)

        # Copy SSL files.
        print cls.machine.ssh("mkdir -p /tmp/kafka-cluster-bridge-test/secrets")
        local_secrets_dir = os.path.join(FIXTURES_DIR, "secrets")
        cls.machine.scp_to_machine(local_secrets_dir, "/tmp/kafka-cluster-bridge-test")

        cls.cluster = utils.TestCluster("cluster-test", FIXTURES_DIR, "cluster-bridged-ssl.yml")
        cls.cluster.start()
        assert "PASS" in cls.cluster.run_command_on_service("zookeeper-1", ZK_READY.format(servers="zookeeper-1:2181,zookeeper-2:2181,zookeeper-3:2181"))

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()
        cls.machine.ssh("sudo rm -rf /tmp/kafka-cluster-bridge-test/secrets")

    def test_bridge_network(self):
        # Test from within the container
        self.is_kafka_healthy_for_service("kafka-ssl-1", 9093, 3, "kafka-ssl-1", "SSL")
        # Test from outside the container
        logs = utils.run_docker_command(
            image="confluentinc/cp-kafkacat",
            command=KAFKA_SSL_CHECK.format(host="kafka-ssl-1", port=9093),
            host_config={'NetworkMode': 'cluster-test_zk', 'Binds': ['/tmp/kafka-cluster-bridge-test/secrets:/etc/kafka/secrets']})

        parsed_logs = json.loads(logs)
        self.assertEquals(3, len(parsed_logs["brokers"]))
        expected_brokers = [{"id": 1, "name": "kafka-ssl-1:9093"}, {"id": 2, "name": "kafka-ssl-2:9093"}, {"id": 3, "name": "kafka-ssl-3:9093"}]
        self.assertEquals(sorted(expected_brokers), sorted(parsed_logs["brokers"]))

        producer_logs = utils.run_docker_command(
            300,
            image="confluentinc/cp-kafka",
            name="kafka-ssl-bridged-producer",
            environment={'KAFKA_ZOOKEEPER_CONNECT': "zookeeper-1:2181,zookeeper-2:2181,zookeeper-3:2181/ssl"},
            command=PRODUCER.format(brokers="kafka-ssl-1:9093", topic="foo", config="bridged.producer.ssl.config", messages=100),
            host_config={'NetworkMode': 'cluster-test_zk', 'Binds': ['/tmp/kafka-cluster-bridge-test/secrets:/etc/kafka/secrets']})

        self.assertTrue("PRODUCED 100 messages" in producer_logs)

        consumer_logs = utils.run_docker_command(
            300,
            image="confluentinc/cp-kafkacat",
            name="kafkacat-ssl-bridged-consumer",
            command=KAFKACAT_SSL_CONSUMER.format(brokers="kafka-ssl-1:9093", topic="foo", messages=10),
            host_config={'NetworkMode': 'cluster-test_zk', 'Binds': ['/tmp/kafka-cluster-bridge-test/secrets:/etc/kafka/secrets']})

        self.assertEquals("\n".join([str(i + 1) for i in xrange(10)]), consumer_logs.strip())


class ClusterSASLBridgedNetworkTest(ClusterBridgedNetworkTest):
    @classmethod
    def setUpClass(cls):
        machine_name = os.environ["DOCKER_MACHINE_NAME"]
        cls.machine = utils.TestMachine(machine_name)

        # Copy SSL files.
        print cls.machine.ssh("mkdir -p /tmp/kafka-cluster-bridge-test/secrets")
        local_secrets_dir = os.path.join(FIXTURES_DIR, "secrets")
        cls.machine.scp_to_machine(local_secrets_dir, "/tmp/kafka-cluster-bridge-test")

        cls.cluster = utils.TestCluster("cluster-test", FIXTURES_DIR, "cluster-bridged-sasl.yml")
        cls.cluster.start()

        # Create keytabs
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="bridged_broker1", principal="kafka", hostname="kafka-sasl-ssl-1"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="bridged_broker2", principal="kafka", hostname="kafka-sasl-ssl-2"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="bridged_broker3", principal="kafka", hostname="kafka-sasl-ssl-3"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="bridged_kafkacat", principal="bridged_kafkacat", hostname="bridged-kafkacat"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="bridged_producer", principal="bridged_producer", hostname="kafka-sasl-ssl-producer"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="bridged_consumer", principal="bridged_consumer", hostname="kafka-sasl-ssl-consumer"))

        assert "PASS" in cls.cluster.run_command_on_service("zookeeper-1", ZK_READY.format(servers="zookeeper-1:2181,zookeeper-2:2181,zookeeper-3:2181"))

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()
        cls.machine.ssh("sudo rm -rf /tmp/kafka-cluster-bridge-test/secrets")

    def test_bridge_network(self):
        # Test from within the container
        self.is_kafka_healthy_for_service("kafka-sasl-ssl-1", 9094, 3, "kafka-sasl-ssl-1", "SASL_SSL")

        # FIXME: Figure out how to use kafkacat with SASL/Kerberos
        # Test from outside the container
        # logs = utils.run_docker_command(
        #     image="confluentinc/cp-kafkacat",
        #     name="bridged-kafkacat",
        #     command=KAFKA_SASL_SSL_CHECK.format(host="kafka-sasl-ssl-1", port=9094, broker_principal="kafka", client_principal="bridged_kafkacat", client_host="bridged-kafkacat"),
        #     host_config={'NetworkMode': 'cluster-test_zk', 'Binds': ['/tmp/kafka-cluster-bridge-test/secrets:/etc/kafka/secrets', '/tmp/kafka-cluster-bridge-test/secrets/bridged_krb.conf:/etc/krb5.conf']})
        #
        # parsed_logs = json.loads(logs)
        # self.assertEquals(3, len(parsed_logs["brokers"]))
        # expected_brokers = [{"id": 1, "name": "kafka-sasl-ssl-1:9094"}, {"id": 2, "name": "kafka-sasl-ssl-2:9094"}, {"id": 3, "name": "kafka-sasl-ssl-3:9094"}]
        # self.assertEquals(sorted(expected_brokers), sorted(parsed_logs["brokers"]))

        producer_env = {'KAFKA_ZOOKEEPER_CONNECT': "zookeeper-1:2181,zookeeper-2:2181,zookeeper-3:2181/saslssl",
                        'KAFKA_OPTS': "-Djava.security.auth.login.config=/etc/kafka/secrets/bridged_producer_jaas.conf -Djava.security.krb5.conf=/etc/kafka/secrets/bridged_krb.conf -Dsun.net.spi.nameservice.provider.1=sun -Dsun.security.krb5.debug=true"}
        producer_logs = utils.run_docker_command(
            300,
            image="confluentinc/cp-kafka",
            name="kafka-sasl-ssl-bridged-producer",
            environment=producer_env,
            command=PRODUCER.format(brokers="kafka-sasl-ssl-1:9094", topic="foo", config="bridged.producer.ssl.sasl.config", messages=100),
            host_config={'NetworkMode': 'cluster-test_zk', 'Binds': ['/tmp/kafka-cluster-bridge-test/secrets:/etc/kafka/secrets']})

        self.assertTrue("PRODUCED 100 messages" in producer_logs)

        consumer_env = {'KAFKA_ZOOKEEPER_CONNECT': "zookeeper-1:2181,zookeeper-2:2181,zookeeper-3:2181/saslssl",
                        'KAFKA_OPTS': "-Djava.security.auth.login.config=/etc/kafka/secrets/bridged_consumer_jaas.conf -Djava.security.krb5.conf=/etc/kafka/secrets/bridged_krb.conf -Dsun.net.spi.nameservice.provider.1=sun -Dsun.security.krb5.debug=true"}

        consumer_logs = utils.run_docker_command(
            300,
            image="confluentinc/cp-kafka",
            name="kafka-sasl-ssl-bridged-consumer",
            environment=consumer_env,
            command=CONSUMER.format(brokers="kafka-sasl-ssl-1:9094", topic="foo", config="bridged.consumer.ssl.sasl.config", messages=10),
            host_config={'NetworkMode': 'cluster-test_zk', 'Binds': ['/tmp/kafka-cluster-bridge-test/secrets:/etc/kafka/secrets']})

        self.assertTrue("Processed a total of 10 messages" in consumer_logs)


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

    def test_host_network(self):
        # Test from within the container
        self.is_kafka_healthy_for_service("kafka-1", 19092, 3)
        # Test from outside the container
        logs = utils.run_docker_command(
            image="confluentinc/cp-kafkacat",
            command=KAFKA_CHECK.format(host="localhost", port=19092),
            host_config={'NetworkMode': 'host'})

        parsed_logs = json.loads(logs)
        self.assertEquals(3, len(parsed_logs["brokers"]))
        expected_brokers = [{"id": 1, "name": "localhost:19092"}, {"id": 2, "name": "localhost:29092"}, {"id": 3, "name": "localhost:39092"}]
        self.assertEquals(sorted(expected_brokers), sorted(parsed_logs["brokers"]))

        client_logs = utils.run_docker_command(
            300,
            image="confluentinc/cp-kafka",
            name="kafka-producer",
            environment={'KAFKA_ZOOKEEPER_CONNECT': "localhost:22181,localhost:32181,localhost:42181"},
            command=PLAIN_CLIENTS.format(brokers="localhost:19092", topic="foo", messages=100),
            host_config={'NetworkMode': 'host'})

        self.assertTrue("Processed a total of 100 messages" in client_logs)


class ClusterSSLHostNetworkTest(ClusterHostNetworkTest):
    @classmethod
    def setUpClass(cls):
        machine_name = os.environ["DOCKER_MACHINE_NAME"]
        cls.machine = utils.TestMachine(machine_name)

        # Copy SSL files.
        print cls.machine.ssh("mkdir -p /tmp/kafka-cluster-host-test/secrets")
        local_secrets_dir = os.path.join(FIXTURES_DIR, "secrets")
        cls.machine.scp_to_machine(local_secrets_dir, "/tmp/kafka-cluster-host-test")

        cls.cluster = utils.TestCluster("cluster-test", FIXTURES_DIR, "cluster-host-ssl.yml")
        cls.cluster.start()

        assert "PASS" in cls.cluster.run_command_on_service("zookeeper-1", ZK_READY.format(servers="localhost:22181,localhost:32181,localhost:42181"))

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()
        cls.machine.ssh("sudo rm -rf /tmp/kafka-cluster-host-test/secrets")

    def test_host_network(self):
        # Test from within the container
        self.is_kafka_healthy_for_service("kafka-ssl-1", 19093, 3, "localhost", "SSL")
        # Test from outside the container
        logs = utils.run_docker_command(
            image="confluentinc/cp-kafkacat",
            command=KAFKA_SSL_CHECK.format(host="localhost", port=19093),
            host_config={'NetworkMode': 'host', 'Binds': ['/tmp/kafka-cluster-host-test/secrets:/etc/kafka/secrets']})

        parsed_logs = json.loads(logs)
        self.assertEquals(3, len(parsed_logs["brokers"]))
        expected_brokers = [{"id": 1, "name": "localhost:19093"}, {"id": 2, "name": "localhost:29093"}, {"id": 3, "name": "localhost:39093"}]
        self.assertEquals(sorted(expected_brokers), sorted(parsed_logs["brokers"]))

        producer_logs = utils.run_docker_command(
            300,
            image="confluentinc/cp-kafka",
            name="kafka-ssl-host-producer",
            environment={'KAFKA_ZOOKEEPER_CONNECT': "localhost:22181,localhost:32181,localhost:42181/ssl"},
            command=PRODUCER.format(brokers="localhost:29093", topic="foo", config="host.producer.ssl.config", messages=100),
            host_config={'NetworkMode': 'host', 'Binds': ['/tmp/kafka-cluster-host-test/secrets:/etc/kafka/secrets']})

        self.assertTrue("PRODUCED 100 messages" in producer_logs)

        consumer_logs = utils.run_docker_command(
            300,
            image="confluentinc/cp-kafkacat",
            name="kafkacat-ssl-host-consumer",
            command=KAFKACAT_SSL_CONSUMER.format(brokers="localhost:29093", topic="foo", messages=10),
            host_config={'NetworkMode': 'host', 'Binds': ['/tmp/kafka-cluster-host-test/secrets:/etc/kafka/secrets']})

        self.assertEquals("\n".join([str(i + 1) for i in xrange(10)]), consumer_logs.strip())


class ClusterSASLHostNetworkTest(ClusterHostNetworkTest):
    @classmethod
    def setUpClass(cls):
        machine_name = os.environ["DOCKER_MACHINE_NAME"]
        cls.machine = utils.TestMachine(machine_name)

        # Add a hostname mapped to eth0, required for SASL to work predictably.
        # localhost and hostname both resolve to 127.0.0.1 in the docker image, so using localhost causes unprodicatable behaviour
        #  with zkclient
        cmd = """
            "sudo sh -c 'grep sasl.kafka.com /etc/hosts || echo {IP} sasl.kafka.com >> /etc/hosts'"
        """.strip()
        cls.machine.ssh(cmd.format(IP=cls.machine.get_internal_ip().strip()))

        # Copy SSL files.
        cls.machine.ssh("mkdir -p /tmp/kafka-cluster-host-test/secrets")

        local_secrets_dir = os.path.join(FIXTURES_DIR, "secrets")
        cls.machine.scp_to_machine(local_secrets_dir, "/tmp/kafka-cluster-host-test")

        cls.cluster = utils.TestCluster("cluster-test", FIXTURES_DIR, "cluster-host-sasl.yml")
        cls.cluster.start()

        # Create keytabs
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="host_broker1", principal="kafka", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="host_broker2", principal="kafka", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="host_broker3", principal="kafka", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="host_producer", principal="host_producer", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="host_consumer", principal="host_consumer", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zookeeper-host-1", principal="zookeeper", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zookeeper-host-2", principal="zookeeper", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zookeeper-host-3", principal="zookeeper", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zkclient-host-1", principal="zkclient", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zkclient-host-2", principal="zkclient", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zkclient-host-3", principal="zkclient", hostname="sasl.kafka.com"))

        assert "PASS" in cls.cluster.run_command_on_service("zookeeper-sasl-1", ZK_READY.format(servers="sasl.kafka.com:22181,sasl.kafka.com:32181,sasl.kafka.com:42181"))

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()
        cls.machine.ssh("sudo rm -rf /tmp/kafka-cluster-host-test/secrets")

    def test_host_network(self):
        # Test from within the container
        self.is_kafka_healthy_for_service("kafka-sasl-ssl-1", 19094, 3, "sasl.kafka.com", "SASL_SSL")

        producer_env = {'KAFKA_ZOOKEEPER_CONNECT': "sasl.kafka.com:22181,sasl.kafka.com:32181,sasl.kafka.com:42181/saslssl",
                        'KAFKA_OPTS': "-Djava.security.auth.login.config=/etc/kafka/secrets/host_producer_jaas.conf -Djava.security.krb5.conf=/etc/kafka/secrets/host_krb.conf -Dsun.net.spi.nameservice.provider.1=sun -Dsun.security.krb5.debug=true"}
        producer_logs = utils.run_docker_command(
            300,
            image="confluentinc/cp-kafka",
            name="kafka-ssl-sasl-host-producer",
            environment=producer_env,
            command=PRODUCER.format(brokers="sasl.kafka.com:29094", topic="foo", config="host.producer.ssl.sasl.config", messages=100),
            host_config={'NetworkMode': 'host', 'Binds': ['/tmp/kafka-cluster-host-test/secrets:/etc/kafka/secrets']})

        self.assertTrue("PRODUCED 100 messages" in producer_logs)

        consumer_env = {'KAFKA_ZOOKEEPER_CONNECT': "sasl.kafka.com:22181,sasl.kafka.com:32181,sasl.kafka.com:42181/saslssl",
                        'KAFKA_OPTS': "-Djava.security.auth.login.config=/etc/kafka/secrets/host_consumer_jaas.conf -Djava.security.krb5.conf=/etc/kafka/secrets/host_krb.conf -Dsun.net.spi.nameservice.provider.1=sun -Dsun.security.krb5.debug=true"}

        consumer_logs = utils.run_docker_command(
            300,
            image="confluentinc/cp-kafka",
            name="kafka-ssl-sasl-host-consumer",
            environment=consumer_env,
            command=CONSUMER.format(brokers="sasl.kafka.com:29094", topic="foo", config="host.consumer.ssl.sasl.config", messages=10),
            host_config={'NetworkMode': 'host', 'Binds': ['/tmp/kafka-cluster-host-test/secrets:/etc/kafka/secrets']})

        self.assertTrue("Processed a total of 10 messages" in consumer_logs)
