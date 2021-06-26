FROM debian:stretch-slim

WORKDIR /build

ENV VERSION=1.3.1-1

ENV BUILD_PACKAGES="build-essential cmake python git curl zlib1g-dev libsasl2-dev libssl-dev"

RUN echo "Building kafkacat ....." \
    && apt-get update -y \
    && DEBIAN_FRONTEND=noninteractive apt-get --no-install-recommends install -y $BUILD_PACKAGES \
    && git clone https://github.com/edenhill/kafkacat \
    && cd kafkacat \
    && git checkout tags/debian/$VERSION \
    && ./bootstrap.sh \
    && make

###

FROM debian:stretch-slim

ARG COMMIT_ID=unknown
LABEL io.confluent.docker.git.id=$COMMIT_ID
ARG BUILD_NUMBER=-1
LABEL io.confluent.docker.build.number=$BUILD_NUMBER
LABEL io.confluent.docker=true

COPY --from=0 /build/kafkacat/kafkacat /usr/local/bin/

RUN apt-get update -y \
    && echo "Installing runtime dependencies for SSL and SASL support ...." \
    && DEBIAN_FRONTEND=noninteractive apt-get --no-install-recommends install -y \
        openssl \
        libssl1.1 \
        libsasl2-2 \
        libsasl2-modules-gssapi-mit \
        krb5-user \
        krb5-config \
        ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

CMD ["kafkacat"]
