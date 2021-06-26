# You can override vars like REPOSITORY in a local.make file
-include local.make

# Bump this on subsequent build, reset on new version or public release. Inherit from env for CI builds.
BUILD_NUMBER ?= 1

CONFLUENT_MAJOR_VERSION ?= 5
CONFLUENT_MINOR_VERSION ?= 3
CONFLUENT_PATCH_VERSION ?= 0

CONFLUENT_VERSION ?= ${CONFLUENT_MAJOR_VERSION}.${CONFLUENT_MINOR_VERSION}.${CONFLUENT_PATCH_VERSION}

KAFKA_VERSION ?= 2.3.0

COMPONENTS := base zookeeper kafka server kafka-rest schema-registry kafka-connect-base kafka-connect server-connect-base server-connect enterprise-control-center kafkacat enterprise-replicator enterprise-replicator-executable enterprise-kafka kafka-mqtt
COMMIT_ID := $(shell git rev-parse --short HEAD)
MYSQL_DRIVER_VERSION := 5.1.39

# Set this variable externally to point at a different repo, such as when building SNAPSHOT images
CONFLUENT_PACKAGES_REPO ?= https://packages.confluent.io

# Set to false for public releases
ALLOW_UNSIGNED ?= false

REPOSITORY ?= confluentinc

# Platform-specific version labels for SNAPSHOT packaging. Not necessary when building from public releases.
CONFLUENT_MVN_LABEL ?=
CONFLUENT_DEB_LABEL ?=
CONFLUENT_RPM_LABEL ?=

# This is used only for the "version" (tag) of images on Docker Hub
VERSION ?= ${CONFLUENT_VERSION}${CONFLUENT_MVN_LABEL}-${BUILD_NUMBER}

clean-containers:
	for container in `docker ps -aq -f label=io.confluent.docker.testing=true` ; do \
        echo "\nRemoving container $${container} \n========================================== " ; \
				docker rm -f $${container} || exit 1 ; \
  done
	# Remove dangling volumes
	docker volume ls -q -f dangling=true | xargs docker volume rm || true;

clean-images:
	for image in `docker images -q -f label=io.confluent.docker.build.number | uniq` ; do \
        echo "Removing image $${image} \n==========================================\n " ; \
				docker rmi -f $${image} || exit 1 ; \
  done

debian/base/include/etc/confluent/docker/docker-utils.jar:
	mkdir -p debian/base/include/etc/confluent/docker
	mvn -U clean compile package -DskipTests \
	&& cp target/docker-utils-${CONFLUENT_VERSION}${CONFLUENT_MVN_LABEL}-jar-with-dependencies.jar debian/base/include/etc/confluent/docker/docker-utils.jar

build-debian: debian/base/include/etc/confluent/docker/docker-utils.jar
	COMPONENTS="${COMPONENTS}" \
	ALLOW_UNSIGNED=${ALLOW_UNSIGNED} \
	CONFLUENT_PACKAGES_REPO=${CONFLUENT_PACKAGES_REPO} \
	KAFKA_VERSION=${KAFKA_VERSION} \
	CONFLUENT_MVN_LABEL=${CONFLUENT_MVN_LABEL} \
	CONFLUENT_DEB_LABEL=${CONFLUENT_DEB_LABEL} \
	CONFLUENT_RPM_LABEL=${CONFLUENT_RPM_LABEL} \
	CONFLUENT_MAJOR_VERSION=${CONFLUENT_MAJOR_VERSION} \
	CONFLUENT_MINOR_VERSION=${CONFLUENT_MINOR_VERSION} \
	CONFLUENT_PATCH_VERSION=${CONFLUENT_PATCH_VERSION} \
	CONFLUENT_VERSION=${CONFLUENT_VERSION} \
	VERSION=${VERSION} \
	COMMIT_ID=${COMMIT_ID} \
	BUILD_NUMBER=${BUILD_NUMBER} \
	REPOSITORY=${REPOSITORY} \
	bin/build-debian

build-test-images:
	for component in `ls tests/images` ; do \
		echo "\n\nBuilding $${component} \n==========================================\n " ; \
		docker build -t ${REPOSITORY}/cp-$${component}:latest tests/images/$${component} || exit 1 ; \
		docker tag ${REPOSITORY}/cp-$${component}:latest ${REPOSITORY}/cp-$${component}:latest || exit 1 ; \
		docker tag ${REPOSITORY}/cp-$${component}:latest ${REPOSITORY}/cp-$${component}:${CONFLUENT_VERSION}${CONFLUENT_MVN_LABEL} || exit 1 ; \
		docker tag ${REPOSITORY}/cp-$${component}:latest ${REPOSITORY}/cp-$${component}:${VERSION} || exit 1 ; \
		docker tag ${REPOSITORY}/cp-$${component}:latest ${REPOSITORY}/cp-$${component}:${COMMIT_ID} || exit 1 ; \
	done

tag-remote:
ifndef DOCKER_REMOTE_REPOSITORY
	$(error DOCKER_REMOTE_REPOSITORY must be defined.)
endif
	for image in `docker images -f label=io.confluent.docker.build.number -f "dangling=false" --format "{{.Repository}}:{{.Tag}}"` ; do \
        echo "\n Tagging $${image} as ${DOCKER_REMOTE_REPOSITORY}/$${image#*/}"; \
        docker tag $${image} ${DOCKER_REMOTE_REPOSITORY}/$${image#*/}; \
  done

push-private: clean build-debian build-test-images tag-remote
ifndef DOCKER_REMOTE_REPOSITORY
	$(error DOCKER_REMOTE_REPOSITORY must be defined.)
endif
	for image in `docker images -f label=io.confluent.docker.build.number -f "dangling=false" --format "{{.Repository}}:{{.Tag}}" | grep $$DOCKER_REMOTE_REPOSITORY` ; do \
        echo "\n Pushing $${image}"; \
        docker push $${image}; \
  done

push-public: clean build-debian
	for component in ${COMPONENTS} ; do \
		echo "\n Pushing cp-$${component}  \n==========================================\n "; \
		docker push ${REPOSITORY}/cp-$${component}:latest || exit 1; \
		docker push ${REPOSITORY}/cp-$${component}:${VERSION} || exit 1; \
		docker push ${REPOSITORY}/cp-$${component}:${CONFLUENT_VERSION} || exit 1; \
  done

clean: clean-containers clean-images
	rm -rf debian/base/include/etc/confluent/docker/docker-utils.jar

venv: venv/bin/activate
venv/bin/activate: tests/requirements.txt
	test -d venv || virtualenv venv
	venv/bin/pip install -Ur tests/requirements.txt
	touch venv/bin/activate

test-build: venv clean build-debian build-test-images
	IMAGE_DIR=$(pwd) venv/bin/py.test tests/test_build.py -v

test-zookeeper: venv clean-containers build-debian build-test-images
	IMAGE_DIR=$(pwd) venv/bin/py.test tests/test_zookeeper.py -v

test-kafka: venv clean-containers build-debian build-test-images
	IMAGE_DIR=$(pwd) venv/bin/py.test tests/test_kafka.py -v

test-schema-registry: venv clean-containers build-debian build-test-images
	IMAGE_DIR=$(pwd) venv/bin/py.test tests/test_schema_registry.py -v

test-kafka-rest: venv clean-containers build-debian build-test-images
	IMAGE_DIR=$(pwd) venv/bin/py.test tests/test_kafka_rest.py -v

tests/fixtures/debian/kafka-connect/jars/mysql-connector-java-${MYSQL_DRIVER_VERSION}-bin.jar:
	mkdir -p tests/fixtures/debian/kafka-connect/jars
	curl -k -SL "https://dev.mysql.com/get/Downloads/Connector-J/mysql-connector-java-${MYSQL_DRIVER_VERSION}.tar.gz" | tar -xzf - -C tests/fixtures/debian/kafka-connect/jars --strip-components=1 mysql-connector-java-${MYSQL_DRIVER_VERSION}/mysql-connector-java-${MYSQL_DRIVER_VERSION}-bin.jar

test-kafka-connect: venv clean-containers build-debian build-test-images tests/fixtures/debian/kafka-connect/jars/mysql-connector-java-${MYSQL_DRIVER_VERSION}-bin.jar
	IMAGE_DIR=$(pwd) venv/bin/py.test tests/test_kafka_connect.py -v

test-enterprise-replicator: venv clean-containers build-debian build-test-images
	IMAGE_DIR=$(pwd) venv/bin/py.test tests/test_enterprise_replicator.py -v

test-enterprise-kafka: venv clean-containers build-debian build-test-images
	IMAGE_DIR=$(pwd) venv/bin/py.test tests/test_enterprise_kafka.py -v

test-control-center: venv clean-containers build-debian build-test-images
	IMAGE_DIR=$(pwd) venv/bin/py.test tests/test_control_center.py -v

test-all: \
	venv \
	clean \
	build-debian \
	build-test-images \
	test-build \
	test-zookeeper \
	test-kafka \
	test-kafka-connect \
	test-enterprise-replicator \
	test-schema-registry \
	test-kafka-rest \
	test-control-center
