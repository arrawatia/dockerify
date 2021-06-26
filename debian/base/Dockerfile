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

FROM debian:jessie

ARG COMMIT_ID=unknown
LABEL io.confluent.docker.git.id=$COMMIT_ID
ARG BUILD_NUMBER=-1
LABEL io.confluent.docker.build.number=$BUILD_NUMBER

ARG CONFLUENT_PACKAGES_REPO=$CONFLUENT_PACKAGES_REPO

ARG ALLOW_UNSIGNED=false
#Set an env var so that it's available in derived images
ENV ALLOW_UNSIGNED=$ALLOW_UNSIGNED

MAINTAINER partner-support@confluent.io
LABEL io.confluent.docker=true

# Python
ENV PYTHON_VERSION="2.7.9-1"
ENV PYTHON_PIP_VERSION="8.1.2"

# Confluent
ENV SCALA_VERSION="2.12"

ARG KAFKA_VERSION=$KAFKA_VERSION
ARG CONFLUENT_MAJOR_VERSION=$CONFLUENT_MAJOR_VERSION
ARG CONFLUENT_MINOR_VERSION=$CONFLUENT_MINOR_VERSION
ARG CONFLUENT_PATCH_VERSION=$CONFLUENT_PATCH_VERSION

ARG CONFLUENT_MVN_LABEL=$CONFLUENT_MVN_LABEL
ARG CONFLUENT_PLATFORM_LABEL=$CONFLUENT_PLATFORM_LABEL

ENV KAFKA_VERSION=$KAFKA_VERSION
ENV CONFLUENT_MAJOR_VERSION=$CONFLUENT_MAJOR_VERSION
ENV CONFLUENT_MINOR_VERSION=$CONFLUENT_MINOR_VERSION
ENV CONFLUENT_PATCH_VERSION=$CONFLUENT_PATCH_VERSION

ENV CONFLUENT_MVN_LABEL=$CONFLUENT_MVN_LABEL
ENV CONFLUENT_PLATFORM_LABEL=$CONFLUENT_PLATFORM_LABEL

ENV CONFLUENT_VERSION="$CONFLUENT_MAJOR_VERSION.$CONFLUENT_MINOR_VERSION.$CONFLUENT_PATCH_VERSION"
ENV CONFLUENT_DEB_VERSION="1"

# Zulu
ENV ZULU_OPENJDK_VERSION="8=8.38.0.13"

# This affects how strings in Java class files are interpreted.  We want UTF-8 and this is the only locale in the
# base image that supports it
ENV LANG="C.UTF-8"

RUN echo "===> Updating debian ....." \
    # TODO debian jessie has been deprecated and is only ex
    && echo "deb http://archive.debian.org/debian/ jessie main" > /etc/apt/sources.list \
    && echo "deb http://security.debian.org jessie/updates main" >> /etc/apt/sources.list \
    && apt-get -qq update \
    \
    && echo "===> Installing curl wget netcat python...." \
    && DEBIAN_FRONTEND=noninteractive apt-get --no-install-recommends install -y \
                apt-transport-https \
                curl \
                gnupg-curl \
                git \
                wget \
                netcat \
                python=${PYTHON_VERSION} \
    && echo "===> Installing python packages ..."  \
    && curl -fSL "https://bootstrap.pypa.io/get-pip.py" | python \
    && pip install --no-cache-dir --upgrade pip==${PYTHON_PIP_VERSION} \
    && pip install --no-cache-dir git+https://github.com/confluentinc/confluent-docker-utils@v0.0.20 \
    && apt remove --purge -y git \
    && echo "Installing Zulu OpenJDK ${ZULU_OPENJDK_VERSION}" \
    && apt-key adv --keyserver hkps://keyserver.ubuntu.com:443 --recv-keys 0x27BC0C8CB3D81623F59BDADCB1998361219BD9C9 \
    && echo "deb http://repos.azulsystems.com/debian stable  main" >> /etc/apt/sources.list.d/zulu.list \
    && apt-get -qq update \
    && apt-get --no-install-recommends install -y zulu-${ZULU_OPENJDK_VERSION} \
    && echo "===> Installing Kerberos Patch ..." \
    && DEBIAN_FRONTEND=noninteractive apt-get --no-install-recommends install -y krb5-user \
    && rm -rf /var/lib/apt/lists/* \
    && echo "===> Adding confluent repository...${CONFLUENT_PACKAGES_REPO}/deb/${CONFLUENT_MAJOR_VERSION}.${CONFLUENT_MINOR_VERSION}" \
    && if [ "x$ALLOW_UNSIGNED" = "xtrue" ]; then echo "APT::Get::AllowUnauthenticated \"true\";" > /etc/apt/apt.conf.d/allow_unauthenticated; else curl -L ${CONFLUENT_PACKAGES_REPO}/deb/${CONFLUENT_MAJOR_VERSION}.${CONFLUENT_MINOR_VERSION}/archive.key | apt-key add - ; fi \
    && echo "deb [arch=amd64] ${CONFLUENT_PACKAGES_REPO}/deb/${CONFLUENT_MAJOR_VERSION}.${CONFLUENT_MINOR_VERSION} stable main" >> /etc/apt/sources.list

ENV CUB_CLASSPATH=/etc/confluent/docker/docker-utils.jar
COPY include/etc/confluent/docker /etc/confluent/docker
