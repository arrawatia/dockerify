#
# Copyright 2017 Confluent Inc.
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

# Extends the Confluent Kafka Connect docker image with a simple
# model for uploading additional connector jars at deployment.
#
# Environment variable is comma-separated list of locations in
# env variable CONNECT_CONNECTOR_REPOS.  See details in 
# cp-retrieve-connector-jars.sh for exact syntax (there are some
# subtleties around default searching in the script).
#

FROM confluentinc/cp-kafka-connect

MAINTAINER partner-support@confluent.io

COPY include/sbin/cp-retrieve-connect-jars.sh  /etc/confluent/docker
COPY include/sbin/run.wrapper                  /etc/confluent/docker

CMD ["/etc/confluent/docker/run.wrapper"]

