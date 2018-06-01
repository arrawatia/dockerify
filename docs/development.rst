.. _development :

Docker Developer Guide
======================

**Table of Contents**

.. contents::
  :local:

.. _image_design_overview :

Image Design Overview
---------------------

In this section we assume some prior knowledge of Docker and of how to write Dockerfiles.  If you'd like to first  on best practices for writing Dockerfiles, we recommend reviewing `Docker's best practices guide <https://docs.docker.com/engine/userguide/eng-image/dockerfile_best-practices/#best-practices-for-writing-dockerfiles>`_.

The Bootup Process
~~~~~~~~~~~~~~~~~~

Upon startup, the entrypoint ``/etc/confluent/docker/run`` runs three executable scripts found in
the ``/etc/confluent/docker``.  They are run in the following sequence:

``/etc/confluent/docker/configure``

``/etc/confluent/docker/ensure``

``/etc/confluent/docker/launch``

Configuration
~~~~~~~~~~~~~

The ``configure`` script does all the necessary configuration for each image. This includes the following:

- Creating all configuration files and copying them to their proper location
- Ensuring that mandatory configuration properties are present
- Handling service discovery (if required)

Preflight Checks
~~~~~~~~~~~~~~~~

The ``ensure`` scripts makes sure that all the prerequisites for
launching the service are in place. This includes:

-  Ensure the configuration files are present and readable.
-  Ensure that you can write/read to the data directory. The directories
   need to be world writable.
-  Ensuring supporting services are in READY state. For example, ensure
   that ZK is ready before launching a Kafka broker.
-  Ensure supporting systems are configured properly. For example, make
   sure all topics required for C3 are created with proper replication,
   security and partition settings.

Launching the Process
~~~~~~~~~~~~~~~~~~~~~

The ``launch`` script runs the actual process. The script should ensure
that :

-  The process is run with process id 1. Your script should use ``exec`` so the program takes over the shell process rather than running as a child process.  This is so that your program will receive signals like SIGTERM directly rather than its parent shell process receiving them.
-  Log to stdout

Development Guidelines
~~~~~~~~~~~~~~~~~~~~~~

We adhered to the following guidelines when developing these Docker bootup scripts:

1. Make it Executable
2. Fail Fast
3. Fail with Good Error Messages
4. Return 0 if success, 1 if fail

.. _setup :

Setup
-----

1. Install Docker.  Here we assume you are running on Mac OS X.  For instructions on installing Docker on Linux or Windows, please refer to the official `Docker Machine documentation <https://docs.docker.com/engine/installation/>`_.

   .. sourcecode:: bash

       brew install docker docker-machine

2. Create a Docker Machine:

  .. sourcecode:: bash

      docker-machine create --driver virtualbox --virtualbox-memory 6000 confluent

  This command will create a local environment but it is recommended that you create one on AWS. The builds are much faster and more predictable (virtualbox stops when you close the lid of the laptop and sometimes gets into a weird state).  When choosing an instance type, ``m4.large`` is good choice. It has 2 vCPUs with 8GB RAM and costs around ~$88 monthly.

  .. sourcecode:: bash

      export INSTANCE_NAME=$USER-docker-machine
      docker-machine create \
         --driver amazonec2 \
         --amazonec2-region us-west-2 \
         --amazonec2-instance-type m4.large \
         --amazonec2-root-size 100 \
         --amazonec2-ami ami-16b1a077 \
         --amazonec2-tags Name,$INSTANCE_NAME \
         $USER-aws-confluent

3. Configure your terminal window to attach it to your new Docker Machine:

   .. sourcecode:: bash

       eval $(docker-machine env confluent)

.. _building_the_images :

Building the Images
~~~~~~~~~~~~~~~~~~~

To get started, you can build all the Confluent Platform images as follows:

  .. sourcecode:: bash

    make build-debian

You can run build tests by running ``make test-build``.  Use this when you want to test the builds with a clean slate.  This deletes all images and starts from scratch.

.. _running_tests :

Running Tests
~~~~~~~~~~~~~

You'll need to first install virtualenv: ``pip install virtualenv``

  .. sourcecode:: bash

      cd cp-docker-images
      make test-zookeeper
      make test-kafka

To run a single test, you can do so with Python.  In the following example, we run only the ``ConfigTest`` found in ``test_zookeeper.py``:

  .. sourcecode:: bash

    venv/bin/py.test tests/test_zookeeper.py::ConfigTest -v

  .. note::

    Deleting All Docker Containers: During the development process, you'll often need to delete and rebuild the Docker images.  You can do so by running ``docker rm -f $(docker ps -a -q)``.


.. _configuring_ci :

Configuring CI
~~~~~~~~~~~~~~

Note: This has been tested on Ubuntu 15.10 only with Docker v1.12.1.

1. Install `Docker<https://docs.docker.com/engine/installation/linux/ubuntulinux>`_. Make sure that the current user can issue `docker` commands by `creating a docker group <https://docs.docker.com/engine/installation/linux/ubuntulinux/#/create-a-docker-group>`_.

2. Install prerequisites.

  .. sourcecode:: bash

    sudo apt-get install -yy git python make python-pip virtualenv maven openjdk-8-jdk

3. Run ``make ci`` to build all the images and run all the tests.


Make Targets
~~~~~~~~~~~~

Delete all images tagged with ``label=io.confluent.docker.testing=true`` :

``clean-images``

Delete all containers tagged with ``label=io.confluent.docker.build.number`` :

``clean-containers``

Tag images for the repository in ``DOCKER_REMOTE_REPOSITORY``:

``tag-remote``

Push images to the private repository:

``push-private``

Push to the Docker hub:

``push-public``

.. _extending_images :

Extending the Docker Images
---------------------------

You may want to extend the images to add new software, change the
config management, use service discovery etc.  This page provides instructions for doing so.

.. _prerequisites :

Prerequisites
~~~~~~~~~~~~~

1. Read the section on :ref:`development <development>` to setup the development environment to build Docker images.
2. Understand how the images are structured by reading the following docs:

   -  ``image-structure`` describes the structure of the images
   -  ``utility_scripts`` describes the utility scripts used in the
      images

3. If you plan to contribute back to the project, see the `contributing guidelines <https://github.com/confluentinc/cp-docker-images/blob/master/CONTRIBUTING.md>`_.

Adding Connectors to the Kafka Connect Image
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are currently two ways to add new connectors to the Kafka Connect image.

* Build a new Docker image that has connector installed. You can follow example 2 in the documentation below. You will need to make sure that the connector jars are on the classpath.
* Add the connector jars via volumes.  If you don't want to create a new Docker image, please see our documentation on `Configuring Kafka Connect with External Jars <operations/external-volumes.html>`_ to configure the `cp-kafka-connect` container with external jars.

.. _examples :

Examples
~~~~~~~~

The following examples show to extend the images.

1. Download configuration from a URL

  This example shows how to change the configuration management. You will need to override the ``configure`` script to download the scripts from an HTTP URL.

  To do this for the |zk| image, you will need the following dockerfile and configure script. This example assumes that each property file is has a URL.

  ``Dockerfile``

  .. sourcecode:: bash

      FROM confluentinc/cp-zookeeper

      COPY include/etc/confluent/docker/configure /etc/confluent/docker/configure

  ``include/etc/confluent/docker/configure``

  .. sourcecode:: bash

      set -o nounset \
          -o errexit \
          -o verbose \
          -o xtrace


      # Ensure that URL locations are available.
      dub ensure ZOOKEEPER_SERVER_CONFIG_URL
      dub ensure ZOOKEEPER_SERVER_ID_URL
      dub ensure ZOOKEEPER_LOG_CONFIG_URL

      # Ensure that the config location is writable.
      dub path /etc/kafka/ writable

      curl -XGET ZOOKEEPER_SERVER_CONFIG_URL > /etc/kafka/zookeeper.properties
      curl -XGET ZOOKEEPER_SERVER_ID_URL > /var/lib/zookeeper/data/myid
      curl -XGET ZOOKEEPER_LOG_CONFIG_URL > /etc/kafka/log4j.properties

      Build the image:

          docker build -t foo/zookeeper:latest .


  Run it :

  .. sourcecode:: bash

      docker run \
           -e ZOOKEEPER_SERVER_CONFIG_URL=http://foo.com/zk1/server.properties \
           -e ZOOKEEPER_SERVER_ID_URL =http://foo.com/zk1/myid \
           -e ZOOKEEPER_LOG_CONFIG_URL =http://foo.com/zk1/log4j.properties \
           foo/zookeeper:latest

2. Add More Software

  This example shows how to add new software to an image. For example, you might want to extend the Kafka Connect client to include the MySQL JDBC driver.

   ``Dockerfile``

   .. sourcecode:: bash

       FROM confluentinc/cp-kafka-connect

       ENV MYSQL_DRIVER_VERSION 5.1.39

       RUN curl -k -SL "https://dev.mysql.com/get/Downloads/Connector-J/mysql-connector-java-${MYSQL_DRIVER_VERSION}.tar.gz" \
           | tar -xzf - -C /usr/share/java/kafka/ --strip-components=1 mysql-connector-java-5.1.39/mysql-connector-java-${MYSQL_DRIVER_VERSION}-bin.jar

   Build the image:

   .. sourcecode:: bash

       docker build -t foo/mysql-connect:latest .

   **This approach can also be used to create images with your own Kafka Connect Plugins.**

3. Logging to volumes

  The images only expose volumes for data and security configuration. But you might want to write to external storage for some use cases. For example: You might want to write the Kafka authorizer logs to a volume for auditing.

  ``Dockerfile``

  .. sourcecode:: bash

      FROM confluentinc/cp-kafka

      # Make sure the log directory is world-writable
      RUN echo "===> Creating authorizer logs dir ..." \
           && mkdir -p /var/log/kafka-auth-logs
           && chmod -R ag+w /var/log/kafka-auth-logs

      VOLUME ["/var/lib/${COMPONENT}/data", "/etc/${COMPONENT}/secrets", "/var/log/kafka-auth-logs"]

      COPY include/etc/confluent/log4j.properties.template /etc/confluent/log4j.properties.template

  ``include/etc/confluent/log4j.properties.template``

  .. sourcecode:: bash

    log4j.rootLogger={{ env["KAFKA_LOG4J_ROOT_LOGLEVEL"] | default('INFO') }}, stdout

    log4j.appender.stdout=org.apache.log4j.ConsoleAppender
    log4j.appender.stdout.layout=org.apache.log4j.PatternLayout
    log4j.appender.stdout.layout.ConversionPattern=[%d] %p %m (%c)%n

    log4j.appender.authorizerAppender=org.apache.log4j.DailyRollingFileAppender
    log4j.appender.authorizerAppender.DatePattern='.'yyyy-MM-dd-HH
    log4j.appender.authorizerAppender.File=/var/log/kafka-auth-logs/kafka-authorizer.log
    log4j.appender.authorizerAppender.layout=org.apache.log4j.PatternLayout
    log4j.appender.authorizerAppender.layout.ConversionPattern=[%d] %p %m (%c)%n

    log4j.additivity.kafka.authorizer.logger=false

    {% set loggers = {
     'kafka': 'INFO',
     'kafka.network.RequestChannel$': 'WARN',
     'kafka.producer.async.DefaultEventHandler': 'DEBUG',
     'kafka.request.logger': 'WARN',
     'kafka.controller': 'TRACE',
     'kafka.log.LogCleaner': 'INFO',
     'state.change.logger': 'TRACE',
     'kafka.authorizer.logger': 'WARN, authorizerAppender'
     } -%}


    {% if env['KAFKA_LOG4J_LOGGERS'] %}
    {% set loggers = parse_log4j_loggers(env['KAFKA_LOG4J_LOGGERS'], loggers) %}
    {% endif %}

  Build the image:

  .. sourcecode:: bash

    docker build -t foo/kafka-auditable:latest .

4. Writing heap and verbose GC logging to external volumes

  You might want to log heap dumps and GC logs to an external volumes for debugging for the Kafka image.

  ``Dockerfile``

  .. sourcecode:: bash

    FROM confluentinc/cp-kafka

    # Make sure the jvm log directory is world-writable
    RUN echo "===> Creating jvm logs dir ..." \
         && mkdir -p /var/log/jvm-logs
         && chmod -R ag+w /var/log/jvm-logs

    VOLUME ["/var/lib/${COMPONENT}/data", "/etc/${COMPONENT}/secrets", "/var/log/jvm-logs"]

  Build the image:

  .. sourcecode:: bash

    docker build -t foo/kafka-verbose-jvm:latest .

  Run it:

  .. sourcecode:: bash

    docker run \
        -e KAFKA_HEAP_OPTS="-Xmx256M -Xloggc:/var/log/jvm-logs/verbose-gc.log -verbose:gc -XX:+PrintGCDateStamps -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/var/log/jvm-logs" \
        foo/kafka-verbose-jvm:latest

5. External Service discovery

  You can extend the images to support for any service discovery mechanism either by overriding relevent properties or by overriding the ``configure`` script as explained in example 1.

  The images support Mesos by overriding relevent proprties for Mesos service discovery. See ``debian/kafka-connect/includes/etc/confluent/docker/mesos-overrides`` for examples.

.. _oracle_jdk :

6. Use Oracle JDK

  The images ship with Azul Zulu OpenJDK.  Due to licensing restrictions, we cannot bundle Oracle JDK, but we are testing on Zulu OpenJDK and do suggest it as a viable alternative.  In the event that you really need to use Oracle's version, you can follow the steps below to modify the images to include Oracle JDK instead of Zulu OpenJDK.

  1. Change the base image to install Oracle JDK instead of Zulu OpenJDK by updating ``debian/base/Dockerfile``.

    .. sourcecode:: bash

       FROM debian:jessie

       ARG COMMIT_ID=unknown
       LABEL io.confluent.docker.git.id=$COMMIT_ID
       ARG BUILD_NUMBER=-1
       LABEL io.confluent.docker.build.number=$BUILD_NUMBER

       MAINTAINER partner-support@confluent.io
       LABEL io.confluent.docker=true


       # Python
       ENV PYTHON_VERSION="2.7.9-1"
       ENV PYTHON_PIP_VERSION="8.1.2"

       # Confluent
       ENV SCALA_VERSION="2.11"
       ENV CONFLUENT_MAJOR_VERSION="4.1"
       ENV CONFLUENT_VERSION="4.1.0"
       ENV CONFLUENT_DEB_VERSION="1"

       # Zulu
       ENV ZULU_OPENJDK_VERSION="8=8.15.0.1"

       # Replace the following lines for Zulu OpenJDK...
       #
       && echo "Installing Zulu OpenJDK ${ZULU_OPENJDK_VERSION}" \
       && apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 0x219BD9C9 \
       && echo "deb http://repos.azulsystems.com/debian stable  main" >> /etc/apt/sources.list.d/zulu.list \
       && apt-get -qq update \
       && apt-get -y install zulu-${ZULU_OPENJDK_VERSION} \
       && rm -rf /var/lib/apt/lists/* \

       # ...with the following lines for Oracle JDK
       #
       && echo "===> Adding webupd8 repository for Oracle JDK..."  \
       && echo "deb http://ppa.launchpad.net/webupd8team/java/ubuntu trusty main" | tee /etc/apt/sources.list.d/webupd8team-java.list \
       && echo "deb-src http://ppa.launchpad.net/webupd8team/java/ubuntu trusty main" | tee -a /etc/apt/sources.list.d/webupd8team-java.list \
       && apt-key adv --keyserver keyserver.ubuntu.com --recv-keys EEA14886 \
       && apt-get update \
       \
       && echo "===> Installing Oracle JDK 8 ..."   \
       && echo debconf shared/accepted-oracle-license-v1-1 select true | debconf-set-selections \
       && echo debconf shared/accepted-oracle-license-v1-1 seen true | debconf-set-selections \
       && DEBIAN_FRONTEND=noninteractive  apt-get install -y --force-yes \
                       oracle-java8-installer \
                       oracle-java8-set-default  \
                       ca-certificates \
       && rm -rf /var/cache/oracle-jdk8-installer \
       && apt-get clean && rm -rf /tmp/* /var/lib/apt/lists/* \

  2. Next, rebuild all the images:

    .. sourcecode:: bash

      make build-debian

.. _utility_scripts :

Utility Scripts
---------------

Given the dependencies between the various Confluent Platform components (e.g. ZK required for Kafka, Kafka and ZK required for Schema Registry, etc.), it is sometimes necessary to be able to check the status of different services.  The following utilities are used during the bootup sequence of the images and in the testing framework.

Docker Utility Belt (dub)
~~~~~~~~~~~~~~~~~~~~~~~~~

1. Template

  .. sourcecode:: bash

    usage: dub template [-h] input output

    Generate template from env vars.

    positional arguments:
      input       Path to template file.
      output      Path of output file.

2. ensure

  .. sourcecode:: bash

    usage: dub ensure [-h] name

    Check if env var exists.

    positional arguments:
      name        Name of env var.

3. wait

  .. sourcecode:: bash

    usage: dub wait [-h] host port timeout

    wait for network service to appear.

    positional arguments:
      host        Host.
      port        Host.
      timeout     timeout in secs.

4. path

  .. sourcecode:: bash

    usage: dub path [-h] path {writable,readable,executable,exists}

    Check for path permissions and existence.

    positional arguments:
      path                  Full path.
      {writable,readable,executable,exists} One of [writable, readable, executable, exists].

5. path-wait

  .. sourcecode:: bash

    usage: dub path-wait [-h] path timeout

    Wait for a path to exist.

    positional arguments:
      path        Full path.
      timeout     Time in secs to wait for the path to exist.

    optional arguments:
      -h, --help  show this help message and exit

Confluent Platform Utility Belt (cub)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. zk-ready

  Used for checking if |zk| is ready.

  .. sourcecode:: bash

    usage: cub zk-ready [-h] connect_string timeout retries wait

    Check if ZK is ready.

    positional arguments:
      connect_string  ZooKeeper connect string.
      timeout         Time in secs to wait for service to be ready.
      retries         No of retries to check if leader election is complete.
      wait            Time in secs between retries

2. kafka-ready

  Used for checking if Kafka is ready.

  .. sourcecode:: bash

    usage: cub kafka-ready [-h] (-b BOOTSTRAP_BROKER_LIST | -z ZOOKEEPER_CONNECT)
                     [-c CONFIG] [-s SECURITY_PROTOCOL]
                     expected_brokers timeout

    Check if Kafka is ready.

    positional arguments:
    expected_brokers      Minimum number of brokers to wait for
    timeout               Time in secs to wait for service to be ready.

    optional arguments:
    -h, --help            show this help message and exit
    -b BOOTSTRAP_BROKER_LIST, --bootstrap_broker_list BOOTSTRAP_BROKER_LIST
                          List of bootstrap brokers.
    -z ZOOKEEPER_CONNECT, --zookeeper_connect ZOOKEEPER_CONNECT
                          ZooKeeper connect string.
    -c CONFIG, --config CONFIG
                          Path to config properties file (required when security
                          is enabled).
    -s SECURITY_PROTOCOL, --security-protocol SECURITY_PROTOCOL
                          Security protocol to use when multiple listeners are
                          enabled.

3. sr-ready

  Used for checking if the Schema Registry is ready.  If you have multiple Schema Registry nodes, you may need to check their availability individually.

  .. sourcecode:: bash

    usage: cub sr-ready [-h] host port timeout

    positional arguments:
      host  Hostname for Schema Registry.
      port     Port for Schema Registry.
      timeout   Time in secs to wait for service to be ready.

3. kr-ready

  Used for checking if the REST Proxy is ready.  If you have multiple REST Proxy nodes, you may need to check their availability individually.

  .. sourcecode:: bash

    usage: cub kr-ready [-h] host port timeout

    positional arguments:
      host  Hostname for REST Proxy.
      port     Port for REST Proxy.
      timeout         Time in secs to wait for service to be ready.


Client Properties
~~~~~~~~~~~~~~~~~

The following properties may be configured when using the ``kafka-ready`` utility described above.

``bootstrap.servers``
  A list of host/port pairs to use for establishing the initial connection to the Kafka cluster. The client will make use of all servers irrespective of which servers are specified here for bootstrapping&mdash;this list only impacts the initial hosts used to discover the full set of servers. This list should be in the form <code>host1:port1,host2:port2,...</code>. Since these servers are just used for the initial connection to discover the full cluster membership (which may change dynamically), this list need not contain the full set of servers (you may want more than one, though, in case a server is down).

  * Type: list
  * Default:
  * Importance: high

``ssl.key.password``
  The password of the private key in the key store file. This is optional for client.

  * Type: password
  * Importance: high

``ssl.keystore.location``
  The location of the key store file. This is optional for client and can be used for two-way authentication for client.

  * Type: string
  * Importance: high

``ssl.keystore.password``
  The store password for the key store file.This is optional for client and only needed if ssl.keystore.location is configured.

  * Type: password
  * Importance: high

``ssl.truststore.location``
  The location of the trust store file.

  * Type: string
  * Importance: high

``ssl.truststore.password``
  The password for the trust store file.

  * Type: password
  * Importance: high

``sasl.kerberos.service.name``
  The Kerberos principal name that Kafka runs as. This can be defined either in Kafka's JAAS config or in Kafka's config.

  * Type: string
  * Importance: medium

``sasl.mechanism``
  SASL mechanism used for client connections. This may be any mechanism for which a security provider is available. GSSAPI is the default mechanism.

  * Type: string
  * Default: "GSSAPI"
  * Importance: medium

``security.protocol``
  Protocol used to communicate with brokers. Valid values are: PLAINTEXT, SSL, SASL_PLAINTEXT, SASL_SSL.

  * Type: string
  * Default: "PLAINTEXT"
  * Importance: medium

``ssl.enabled.protocols``
  The list of protocols enabled for SSL connections.

  * Type: list
  * Default: [TLSv1.2, TLSv1.1, TLSv1]
  * Importance: medium

``ssl.keystore.type``
  The file format of the key store file. This is optional for client.

  * Type: string
  * Default: "JKS"
  * Importance: medium

``ssl.protocol``
  The SSL protocol used to generate the SSLContext. Default setting is TLS, which is fine for most cases. Allowed values in recent JVMs are TLS, TLSv1.1 and TLSv1.2. SSL, SSLv2 and SSLv3 may be supported in older JVMs, but their usage is discouraged due to known security vulnerabilities.

  * Type: string
  * Default: "TLS"
  * Importance: medium

``ssl.provider``
  The name of the security provider used for SSL connections. Default value is the default security provider of the JVM.

  * Type: string
  * Importance: medium

``ssl.truststore.type``
  The file format of the trust store file.

  * Type: string
  * Default: "JKS"
  * Importance: medium

``sasl.kerberos.kinit.cmd``
  Kerberos kinit command path.

  * Type: string
  * Default: "/usr/bin/kinit"
  * Importance: low

``sasl.kerberos.min.time.before.relogin``
  Login thread sleep time between refresh attempts.

  * Type: long
  * Default: 60000
  * Importance: low

``sasl.kerberos.ticket.renew.jitter``
  Percentage of random jitter added to the renewal time.

  * Type: double
  * Default: 0.05
  * Importance: low

``sasl.kerberos.ticket.renew.window.factor``
  Login thread will sleep until the specified window factor of time from last refresh to ticket's expiry has been reached, at which time it will try to renew the ticket.

  * Type: double
  * Default: 0.8
  * Importance: low

``ssl.cipher.suites``
  A list of cipher suites. This is a named combination of authentication, encryption, MAC and key exchange algorithm used to negotiate the security settings for a network connection using TLS or SSL network protocol.By default all the available cipher suites are supported.

  * Type: list
  * Importance: low

``ssl.endpoint.identification.algorithm``
  The endpoint identification algorithm to validate server hostname using server certificate.

  * Type: string
  * Importance: low

``ssl.keymanager.algorithm``
  The algorithm used by key manager factory for SSL connections. Default value is the key manager factory algorithm configured for the Java Virtual Machine.

  * Type: string
  * Default: "SunX509"
  * Importance: low

``ssl.trustmanager.algorithm``
  The algorithm used by trust manager factory for SSL connections. Default value is the trust manager factory algorithm configured for the Java Virtual Machine.

  * Type: string
  * Default: "PKIX"
  * Importance: low

.. _references :

References
----------

- Docker's example for `setting up a Dockerized AWS EC2 instance <https://docs.docker.com/machine/examples/aws/>`_.
