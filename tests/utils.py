import docker
import os
import time
from compose.container import Container
from compose.config.config import ConfigDetails
from compose.config.config import ConfigFile
from compose.config.config import load
from compose.project import Project
from compose.cli.docker_client import docker_client
from compose.config.environment import Environment
from compose.container import Container
import json
import subprocess


def get_docker_client():
    use_local_docker = os.environ.get("CONFLUENT_USE_LOCAL_DOCKER")
    if use_local_docker:
        return docker.Client()
    else:
        return docker.from_env(assert_hostname=False)


def build_image(image_name, dockerfile_dir):
    print("Building image %s from %s" % (image_name, dockerfile_dir))
    client = get_docker_client()
    output = client.build(dockerfile_dir, rm=True, tag=image_name)
    response = "".join(["     %s" % (line,) for line in output])
    print(response)


def image_exists(image_name):
    client = get_docker_client()
    tags = [t for image in client.images() for t in image['RepoTags']]
    return "%s:%s" % (image_name, "latest") in tags


def pull_image(image_name):
    client = get_docker_client()
    if not image_exists(image_name):
        client.pull(image_name)


def run_docker_command(timeout=None, **kwargs):
    pull_image(kwargs["image"])
    client = get_docker_client()
    kwargs["labels"] = {"io.confluent.docker.testing": "true"}
    container = TestContainer.create(client, **kwargs)
    container.start()
    container.wait(timeout)
    logs = container.logs()
    print "Running command %s: %s" % (kwargs["command"], logs)
    container.shutdown()
    return logs


def path_exists_in_image(image, path):
    print "Checking for %s in %s" % (path, image)
    cmd = "bash -c '[ ! -e %s ] || echo success' " % (path,)
    output = run_docker_command(image=image, command=cmd)
    return "success" in output


def executable_exists_in_image(image, path):
    print "Checking for %s in %s" % (path, image)
    cmd = "bash -c '[ ! -x %s ] || echo success' " % (path,)
    output = run_docker_command(image=image, command=cmd)
    return "success" in output


def run_command_on_host(command):
    logs = run_docker_command(
        image="busybox",
        command=command,
        host_config={'NetworkMode': 'host', 'Binds': ['/tmp:/tmp']})
    print "Running command %s: %s" % (command, logs)
    return logs


class TestContainer(Container):

    def state(self):
        return self.inspect_container["State"]

    def status(self):
        return self.state()["Status"]

    def shutdown(self):
        self.stop()
        self.remove()

    def execute(self, command):
        eid = self.create_exec(command)
        return self.start_exec(eid)

    def wait(self, timeout):
        return self.client.wait(self.id, timeout)


class TestCluster():

    def __init__(self, name, working_dir, config_file):
        config_file_path = os.path.join(working_dir, config_file)
        cfg_file = ConfigFile.from_filename(config_file_path)
        c = ConfigDetails(working_dir, [cfg_file],)
        self.cd = load(c)
        self.name = name

    def get_project(self):
        # Dont reuse the client to fix this bug : https://github.com/docker/compose/issues/1275
        client = docker_client(Environment())
        project = Project.from_config(self.name, self.cd, client)
        return project

    def start(self):
        self.get_project().up()

    def is_running(self):
        state = [container.is_running for container in self.get_project().containers()]
        return all(state) and len(state) > 0

    def is_service_running(self, service_name):
        return self.get_container(service_name).is_running

    def shutdown(self):
        project = self.get_project()
        project.stop()
        project.remove_stopped()

    def get_container(self, service_name, stopped=False):
        return self.get_project().get_service(service_name).get_container()

    def exit_code(self, service_name):
        containers = self.get_project().containers([service_name], stopped=True)
        return containers[0].exit_code

    def wait(self, service_name, timeout):
        container = self.get_project().containers([service_name], stopped=True)
        if container[0].is_running:
            return self.get_project().client.wait(container[0].id, timeout)

    def run_command_on_service(self, service_name, command):
        return self.run_command(command, self.get_container(service_name))

    def service_logs(self, service_name, stopped=False):
        if stopped:
            containers = self.get_project().containers([service_name], stopped=True)
            print(containers[0].logs())
            return containers[0].logs()
        else:
            return self.get_container(service_name).logs()

    def run_command(self, command, container):
        print "Running %s on %s :" % (command, container)
        eid = container.create_exec(command)
        output = container.start_exec(eid)
        print "\n%s " % output
        return output

    def run_command_on_all(self, command):
        results = {}
        for container in self.get_project().containers():
            results[container.name_without_project] = self.run_command(command, container)

        return results


class TestMachine():

    def __init__(self, machine_name):
        self.machine_name = machine_name
        self.use_local_docker = os.environ.get("CONFLUENT_USE_LOCAL_DOCKER")
        if not self.use_local_docker:
            # Ensure docker-machine is installed
            subprocess.check_call("type docker-machine", shell=True)
            # Ensure the machine is ready.
            assert self.status() == "Running"

    def run_cmd(self, cmd):
        print("Running SSH command: %s" % cmd)
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        return output

    def status(self):
        cmd = "docker-machine status %s " % self.machine_name
        return self.run_cmd(cmd).strip()

    def get_internal_ip(self, nw_interface="eth0"):
        if self.use_local_docker:
            cmd = "/sbin/ifconfig %s | grep 'inet addr:' | cut -d: -f2 | awk '{ print $1}'" % nw_interface
        else:
            cmd = "docker-machine ssh %s /sbin/ifconfig %s | grep 'inet addr:' | cut -d: -f2 | awk '{ print $1}'" % (self.machine_name, nw_interface)
        return self.run_cmd(cmd)

    def scp_to_machine(self, local_path, machine_path, recursive=True):
        if recursive:
            recursive_flag = "-r"
        if self.use_local_docker:
            cmd = "cp %s %s %s" % (recursive_flag, local_path, machine_path)
        else:
            cmd = "docker-machine scp %s %s %s:%s" % (recursive_flag, local_path, self.machine_name, machine_path)
        return self.run_cmd(cmd)

    def ssh(self, command):
        if self.use_local_docker:
            if command.startswith('"'):
                cmd = "bash -c %s" % command
            else:
                cmd = command
        else:
            cmd = "docker-machine ssh %s %s" % (self.machine_name, command)
        return self.run_cmd(cmd)
