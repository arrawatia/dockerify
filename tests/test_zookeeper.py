import os
import unittest
import utils
import time
import string

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(CURRENT_DIR, "fixtures", "debian", "zookeeper")
MODE_COMMAND = "bash -c 'dub wait localhost {port} 30 && echo stat | nc localhost {port} | grep Mode'"
HEALTH_CHECK = "bash -c 'cub zk-ready {host}:{port} 30 && echo PASS || echo FAIL'"
JMX_CHECK = """bash -c "\
    echo 'get -b org.apache.ZooKeeperService:name0=StandaloneServer_port{client_port} Version' |
        java -jar jmxterm-1.0-alpha-4-uber.jar -l {jmx_hostname}:{jmx_port} -n -v silent "
"""
KADMIN_KEYTAB_CREATE = """bash -c \
        'kadmin.local -q "addprinc -randkey {principal}/{hostname}@TEST.CONFLUENT.IO" && \
        kadmin.local -q "ktadd -norandkey -k /tmp/keytab/{filename}.keytab {principal}/{hostname}@TEST.CONFLUENT.IO"'
        """


class ConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        machine_name = os.environ["DOCKER_MACHINE_NAME"]
        cls.machine = utils.TestMachine(machine_name)

        # Create directories with the correct permissions for test with userid and external volumes.
        utils.run_command_on_host(
            "mkdir -p /tmp/zk-config-kitchen-sink-test/data /tmp/zk-config-kitchen-sink-test/log")
        utils.run_command_on_host(
            "chown -R 12345 /tmp/zk-config-kitchen-sink-test/data /tmp/zk-config-kitchen-sink-test/log")

        # Copy SSL files.
        cls.machine.ssh("mkdir -p /tmp/zookeeper-config-test/secrets")
        local_secrets_dir = os.path.join(FIXTURES_DIR, "secrets")
        cls.machine.scp_to_machine(local_secrets_dir, "/tmp/zookeeper-config-test")

        cls.cluster = utils.TestCluster("config-test", FIXTURES_DIR, "standalone-config.yml")
        cls.cluster.start()

        # Create keytabs
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zookeeper-config", principal="zookeeper", hostname="sasl-config"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zkclient-config", principal="zkclient", hostname="sasl-config"))

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()
        utils.run_command_on_host("rm -rf /tmp/zk-config-kitchen-sink-test")
        utils.run_command_on_host(" rm -rf /tmp/zookeeper-config-test")

    @classmethod
    def is_zk_healthy_for_service(cls, service, client_port, host="localhost"):
        output = cls.cluster.run_command_on_service(service, HEALTH_CHECK.format(port=client_port, host=host))
        assert "PASS" in output

    def test_required_config_failure(self):
        self.assertTrue("ZOOKEEPER_CLIENT_PORT is required." in self.cluster.service_logs("failing-config", stopped=True))
        self.assertTrue("ZOOKEEPER_SERVER_ID is required." in self.cluster.service_logs("failing-config-server-id", stopped=True))

    def test_default_config(self):
        self.is_zk_healthy_for_service("default-config", 2181)
        import string
        zk_props = self.cluster.run_command_on_service("default-config", "cat /etc/kafka/zookeeper.properties")
        expected = """clientPort=2181
            dataDir=/var/lib/zookeeper/data
            dataLogDir=/var/lib/zookeeper/log
            """
        self.assertEquals(zk_props.translate(None, string.whitespace), expected.translate(None, string.whitespace))

    def test_default_logging_config(self):
        self.is_zk_healthy_for_service("default-config", 2181)

        log4j_props = self.cluster.run_command_on_service("default-config", "cat /etc/kafka/log4j.properties")
        expected_log4j_props = """log4j.rootLogger=INFO, stdout

            log4j.appender.stdout=org.apache.log4j.ConsoleAppender
            log4j.appender.stdout.layout=org.apache.log4j.PatternLayout
            log4j.appender.stdout.layout.ConversionPattern=[%d] %p %m (%c)%n
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
        self.is_zk_healthy_for_service("full-config", 22181)
        zk_props = self.cluster.run_command_on_service("full-config", "cat /etc/kafka/zookeeper.properties")
        expected = """clientPort=22181
                dataDir=/var/lib/zookeeper/data
                dataLogDir=/var/lib/zookeeper/log

                initLimit=25
                autopurge.purgeInterval=2
                syncLimit=20
                autopurge.snapRetainCount=4
                tickTime=5555
                quorumListenOnAllIPs=false
                """
        self.assertEquals(zk_props.translate(None, string.whitespace), expected.translate(None, string.whitespace))

        zk_id = self.cluster.run_command_on_service("full-config", "cat /var/lib/zookeeper/data/myid")
        self.assertEquals(zk_id, "1")

    def test_full_logging_config(self):
        self.is_zk_healthy_for_service("full-config", 22181)

        log4j_props = self.cluster.run_command_on_service("full-config", "cat /etc/kafka/log4j.properties")
        expected_log4j_props = """log4j.rootLogger=WARN, stdout

            log4j.appender.stdout=org.apache.log4j.ConsoleAppender
            log4j.appender.stdout.layout=org.apache.log4j.PatternLayout
            log4j.appender.stdout.layout.ConversionPattern=[%d] %p %m (%c)%n

            log4j.logger.zookeeper.foo.bar=DEBUG, stdout
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
        self.is_zk_healthy_for_service("external-volumes", 2181)

    def test_sasl_config(self):
        self.is_zk_healthy_for_service("sasl-config", 52181, "sasl-config")

    def test_random_user(self):
        self.is_zk_healthy_for_service("random-user", 2181)

    def test_kitchen_sink(self):
        self.is_zk_healthy_for_service("kitchen-sink", 22181)
        zk_props = self.cluster.run_command_on_service("kitchen-sink", "cat /etc/kafka/zookeeper.properties")
        expected = """clientPort=22181
                    dataDir=/var/lib/zookeeper/data
                    dataLogDir=/var/lib/zookeeper/log

                    initLimit=25
                    syncLimit=20
                    tickTime=5555
                    quorumListenOnAllIPs=false
                    """
        self.assertTrue(zk_props.translate(None, string.whitespace) == expected.translate(None, string.whitespace))

        zk_id = self.cluster.run_command_on_service("full-config", "cat /var/lib/zookeeper/data/myid")
        self.assertTrue(zk_id == "1")


class StandaloneNetworkingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cluster = utils.TestCluster("standalone-network-test", FIXTURES_DIR, "standalone-network.yml")
        cls.cluster.start()

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()

    @classmethod
    def is_zk_healthy_for_service(cls, service, client_port, host="localhost"):
        output = cls.cluster.run_command_on_service(service, HEALTH_CHECK.format(port=client_port, host=host))
        assert "PASS" in output

    def test_bridge_network(self):
        # Test from within the container
        self.is_zk_healthy_for_service("bridge-network", 2181)
        # Test from outside the container
        logs = utils.run_docker_command(
            image="confluentinc/cp-zookeeper",
            command=HEALTH_CHECK.format(port=22181, host="localhost"),
            host_config={'NetworkMode': 'host'})
        self.assertTrue("PASS" in logs)

    def test_host_network(self):
        # Test from within the container
        self.is_zk_healthy_for_service("host-network", 32181)
        # Test from outside the container
        logs = utils.run_docker_command(
            image="confluentinc/cp-zookeeper",
            command=HEALTH_CHECK.format(port=32181, host="localhost"),
            host_config={'NetworkMode': 'host'})
        self.assertTrue("PASS" in logs)

    def test_jmx_host_network(self):

        # Test from outside the container
        logs = utils.run_docker_command(
            image="confluentinc/cp-jmxterm",
            command=JMX_CHECK.format(client_port=52181, jmx_hostname="localhost", jmx_port="39999"),
            host_config={'NetworkMode': 'host'})
        self.assertTrue("Version = 3.4.10-39d3a4f269333c922ed3db283be479f9deacaa0f, built on 03/23/2017 10:13 GMT;" in logs)

    def test_jmx_bridged_network(self):

        # Test from outside the container
        logs = utils.run_docker_command(
            image="confluentinc/cp-jmxterm",
            command=JMX_CHECK.format(client_port=2181, jmx_hostname="bridge-network-jmx", jmx_port="9999"),
            host_config={'NetworkMode': 'standalone-network-test_zk'})
        self.assertTrue("Version = 3.4.10-39d3a4f269333c922ed3db283be479f9deacaa0f, built on 03/23/2017 10:13 GMT;" in logs)


class ClusterBridgeNetworkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        machine_name = os.environ["DOCKER_MACHINE_NAME"]
        cls.machine = utils.TestMachine(machine_name)

        # Copy SSL files.
        cls.machine.ssh("mkdir -p /tmp/zookeeper-bridged-test/secrets")
        local_secrets_dir = os.path.join(FIXTURES_DIR, "secrets")
        cls.machine.scp_to_machine(local_secrets_dir, "/tmp/zookeeper-bridged-test")

        cls.cluster = utils.TestCluster("cluster-test", FIXTURES_DIR, "cluster-bridged.yml")
        cls.cluster.start()

        # Create keytabs
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zookeeper-bridged-1", principal="zookeeper", hostname="zookeeper-sasl-1"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zookeeper-bridged-2", principal="zookeeper", hostname="zookeeper-sasl-2"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zookeeper-bridged-3", principal="zookeeper", hostname="zookeeper-sasl-3"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zkclient-bridged-1", principal="zkclient", hostname="zookeeper-sasl-1"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zkclient-bridged-2", principal="zkclient", hostname="zookeeper-sasl-2"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zkclient-bridged-3", principal="zkclient", hostname="zookeeper-sasl-3"))

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()
        utils.run_command_on_host("rm -rf /tmp/zookeeper-bridged-test")

    def test_cluster_running(self):
        self.assertTrue(self.cluster.is_running())

    @classmethod
    def is_zk_healthy_for_service(cls, service, client_port, host="localhost"):
        output = cls.cluster.run_command_on_service(service, HEALTH_CHECK.format(port=client_port, host=host))
        assert "PASS" in output

    def test_zookeeper_on_service(self):
        self.is_zk_healthy_for_service("zookeeper-1", 2181, "zookeeper-1")
        self.is_zk_healthy_for_service("zookeeper-1", 2181, "zookeeper-2")
        self.is_zk_healthy_for_service("zookeeper-1", 2181, "zookeeper-3")

        client_ports = [22181, 32181, 42181]
        expected = sorted(["Mode: follower\n", "Mode: follower\n", "Mode: leader\n"])
        outputs = []

        for port in client_ports:
            output = utils.run_docker_command(
                image="confluentinc/cp-zookeeper",
                command=MODE_COMMAND.format(port=port),
                host_config={'NetworkMode': 'host'})
            outputs.append(output)
        self.assertEquals(sorted(outputs), expected)

    def test_sasl_on_service(self):
        self.is_zk_healthy_for_service("zookeeper-sasl-1", 2181, "zookeeper-sasl-1")
        self.is_zk_healthy_for_service("zookeeper-sasl-2", 2181, "zookeeper-sasl-2")
        self.is_zk_healthy_for_service("zookeeper-sasl-3", 2181, "zookeeper-sasl-3")

        # Trying to connect from one container to another  doesnot work because
        # zk code resolves the dns name to the internal docker container name
        # which causes the kerberos authentication to fail.

        # Connect to zookeeper-sasl-2 & zookeeper-sasl-3 from zookeeper-sasl-1
        # self.is_zk_healthy_for_service("zookeeper-sasl-1", 2181, "zookeeper-sasl-2")
        # self.is_zk_healthy_for_service("zookeeper-sasl-1", 2181, "zookeeper-sasl-3")


class ClusterHostNetworkTest(unittest.TestCase):
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
        cls.machine.ssh("mkdir -p /tmp/zookeeper-host-test/secrets")
        local_secrets_dir = os.path.join(FIXTURES_DIR, "secrets")
        cls.machine.scp_to_machine(local_secrets_dir, "/tmp/zookeeper-host-test")

        cls.cluster = utils.TestCluster("cluster-test", FIXTURES_DIR, "cluster-host.yml")
        cls.cluster.start()

        # Create keytabs
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zookeeper-host-1", principal="zookeeper", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zookeeper-host-2", principal="zookeeper", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zookeeper-host-3", principal="zookeeper", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zkclient-host-1", principal="zkclient", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zkclient-host-2", principal="zkclient", hostname="sasl.kafka.com"))
        cls.cluster.run_command_on_service("kerberos", KADMIN_KEYTAB_CREATE.format(filename="zkclient-host-3", principal="zkclient", hostname="sasl.kafka.com"))

    @classmethod
    def tearDownClass(cls):
        cls.cluster.shutdown()
        utils.run_command_on_host("rm -rf /tmp/zookeeper-host-test")

    def test_cluster_running(self):
        self.assertTrue(self.cluster.is_running())

    @classmethod
    def is_zk_healthy_for_service(cls, service, client_port, host="sasl.kafka.com"):
        output = cls.cluster.run_command_on_service(service, HEALTH_CHECK.format(port=client_port, host=host))
        assert "PASS" in output

    def test_zookeeper_on_service(self):
        self.is_zk_healthy_for_service("zookeeper-1", 22182)
        self.is_zk_healthy_for_service("zookeeper-1", 32182)
        self.is_zk_healthy_for_service("zookeeper-1", 42182)

        client_ports = [22182, 32182, 42182]
        expected = sorted(["Mode: follower\n", "Mode: follower\n", "Mode: leader\n"])
        outputs = []
        for port in client_ports:
            output = utils.run_docker_command(
                image="confluentinc/cp-zookeeper",
                command=MODE_COMMAND.format(port=port),
                host_config={'NetworkMode': 'host'})
            outputs.append(output)
        self.assertEquals(sorted(outputs), expected)

    def test_sasl_on_service(self):
        self.is_zk_healthy_for_service("zookeeper-sasl-1", 22182)
        self.is_zk_healthy_for_service("zookeeper-sasl-1", 32182)
        self.is_zk_healthy_for_service("zookeeper-sasl-1", 42182)
