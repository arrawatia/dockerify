#
# Copyright 2016 Confluent Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Builds a docker image for Kafka Connect

FROM confluentinc/cp-kafka

MAINTAINER partner-support@confluent.io
LABEL io.confluent.docker=true
ARG COMMIT_ID=unknown
LABEL io.confluent.docker.git.id=$COMMIT_ID
ARG BUILD_NUMBER=-1
LABEL io.confluent.docker.build.number=$BUILD_NUMBER

ENV COMPONENT=kafka-connect

# Default kafka-connect rest.port
EXPOSE 8083

RUN echo "===> Installing Schema Registry (for Avro jars) ..." \
    && apt-get -qq update \
    && apt-get --no-install-recommends install -y \
        confluent-schema-registry=${CONFLUENT_VERSION}${CONFLUENT_PLATFORM_LABEL}-${CONFLUENT_DEB_VERSION} \
    && echo "===> Installing Controlcenter for monitoring interceptors ..."\
    && apt-get --no-install-recommends install -y confluent-control-center=${CONFLUENT_VERSION}${CONFLUENT_PLATFORM_LABEL}-${CONFLUENT_DEB_VERSION} \
    && echo "===> Installing Confluent Hub client ..."\
    && apt-get --no-install-recommends install -y confluent-hub-client=${CONFLUENT_VERSION}${CONFLUENT_PLATFORM_LABEL}-${CONFLUENT_DEB_VERSION} \
    && echo "===> Cleaning up ..."  \
    && apt-get clean && rm -rf /tmp/* /var/lib/apt/lists/* \
    echo "===> Setting up ${COMPONENT} dirs ..." \
    && mkdir -p /etc/${COMPONENT} /etc/${COMPONENT}/secrets /etc/${COMPONENT}/jars \
    && chmod -R ag+w /etc/${COMPONENT} /etc/${COMPONENT}/secrets /etc/${COMPONENT}/jars

ENV CONNECT_PLUGIN_PATH=/usr/share/java/,/usr/share/confluent-hub-components/

VOLUME ["/etc/${COMPONENT}/jars", "/etc/${COMPONENT}/secrets"]

COPY include/etc/confluent/docker /etc/confluent/docker

CMD ["/etc/confluent/docker/run"]

# Polling period  : 5 seconds
# Timeout period  :10 seconds (if the polling does not return within this time, treat as a failed poll)
# Start-up period : 2 minutes (during which failures are not counted as failures)
# Retry period    : 8 minutes (after which container is deemed unhealthy)
# All settings can be overriden at run-time in Docker/Docker Compose. 
HEALTHCHECK --start-period=120s --interval=5s --timeout=10s --retries=96 \
	CMD /etc/confluent/docker/healthcheck.sh
