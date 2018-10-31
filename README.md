Docker Images for Confluent Plaform
===

Docker images for deploying and running the Confluent Platform.  The images are currently available on [DockerHub](https://hub.docker.com/u/confluentinc/).  They are currently only available for Confluent Platform 3.0.1 and after.

Full documentation for using the images can be found [here](http://docs.confluent.io/current/cp-docker-images/docs/intro.html).

# Deprecation Notice

This is used for building images for version 4.1.x or lower, and should not be used for adding new images. If any new
images is added, please make sure to add to our [Release steps](https://confluentinc.atlassian.net/wiki/x/ywE6Cg) as
they are hardcoded for now (fix is coming soon).

For any new images, they should be added to the repo itself by following [Docker Build Integration](https://confluentinc.atlassian.net/wiki/x/PIDaC)

# Important Caveat - Images Not Tested for Docker for Mac or Windows
[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fconfluentinc%2Fcp-docker-images.svg?type=shield)](https://app.fossa.io/projects/git%2Bgithub.com%2Fconfluentinc%2Fcp-docker-images?ref=badge_shield)

	
These images are not tested on Docker for Mac or Docker for Windows. These images will be updated in the near future to support these platforms. For more details on these known issues, you can refer to the following links:

* [Hostname Issue](https://forums.docker.com/t/docker-for-mac-does-not-add-docker-hostname-to-etc-hosts/8620/4)
* Host networking on Docker for Mac: [link 1](https://forums.docker.com/t/should-docker-run-net-host-work/14215), [link 2](https://forums.docker.com/t/net-host-does-not-work/17378/7), [link 3](https://forums.docker.com/t/explain-networking-known-limitations-explain-host/15205/4)

# Networking and Kafka on Docker

When running Kafka under Docker, you need to pay careful attention to your configuration of hosts and ports to enable components both internal and external to the docker network to communicate. You can see more details in [this article](https://rmoff.net/2018/08/02/kafka-listeners-explained/).

# Building
Use `make` to perform various builds and tests

# Contribute

Start by reading our guidelines on contributing to this project found [here](http://docs.confluent.io/current/cp-docker-images/docs/contributing.html).

- Source Code: https://github.com/confluentinc/cp-docker-images
- Issue Tracker: https://github.com/confluentinc/cp-docker-images/issues


# License

The project is licensed under the Apache 2 license. For more information on the licenses for each of the individual Confluent Platform components packaged in the images, please refer to the respective [Confluent Platform documentation for each component](http://docs.confluent.io/current/platform.html).  



[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fconfluentinc%2Fcp-docker-images.svg?type=large)](https://app.fossa.io/projects/git%2Bgithub.com%2Fconfluentinc%2Fcp-docker-images?ref=badge_large)