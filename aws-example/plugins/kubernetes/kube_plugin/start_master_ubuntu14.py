from cloudify.decorators import operation
from kube_plugin import get_docker,edit_docker_config
from cloudify import ctx
import os
import subprocess
import time


@operation
def start_master(**kwargs):
  os.chdir(os.path.expanduser("~"))

  # Install Docker
  subprocess.call("sudo apt-get install apt-transport-https ca-certificates",shell=True)
  subprocess.call("sudo apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 58118E89F3A912897C070ADBF76221572C52609D",shell=True)

  subprocess.call("sudo apt-get install apparmor",shell=True)

  subprocess.call("sudo touch /etc/apt/sources.list.d/docker.list",shell=True)
  subprocess.call("sudo bash -c 'echo \"deb https://apt.dockerproject.org/repo ubuntu-trusty main\" > /etc/apt/sources.list.d/docker.list'",shell=True)

  subprocess.call("sudo apt-get update",shell=True)
  subprocess.call("sudo apt-get purge lxc-docker",shell=True)
  subprocess.call("sudo apt-cache policy docker-engine",shell=True)
  subprocess.call("sudo apt-get --assume-yes install linux-image-extra-$(uname -r)",shell=True)


  subprocess.call("sudo apt-get --assume-yes install docker-engine",shell=True)

  subprocess.call("service docker start",shell=True)

  master_port=ctx.node.properties['master_port']

  ctx.logger.info("in start_master")

  subprocess.Popen(['sudo','nohup','docker','daemon','-H','unix:///var/run/docker-bootstrap.sock','-p','/var/run/docker-bootstrap.pid','--iptables=false','--ip-masq=false','--bridge=none','--graph=/var/lib/docker-bootstrap'],stdout=open('/dev/null'),stderr=open('/tmp/docker-bootstrap.log','w'),stdin=open('/dev/null'))
  time.sleep(2)

  # start etcd
  res=os.system("sudo docker -H unix:///var/run/docker-bootstrap.sock run -d --net=host gcr.io/google_containers/etcd-amd64:2.2.1 /usr/local/bin/etcd --listen-client-urls=http://127.0.0.1:4001 -advertise-client-urls=http://127.0.0.1:4001 --data-dir=/var/etcd/data")

  ctx.logger.info("start etcd:"+str(res))

  time.sleep(2)

  # set cidr range for flannel
  os.system("sudo docker -H unix:///var/run/docker-bootstrap.sock run --net=host gcr.io/google_containers/etcd-amd64:2.2.1 etcdctl set /coreos.com/network/config '{ \"Network\": \"10.1.0.0/16\"}'")

  ctx.logger.info("set flannel cidr")

  # stop docker

  os.system("sudo service docker stop")

  #run flannel

  pipe=subprocess.Popen(['sudo','docker','-H','unix:///var/run/docker-bootstrap.sock','run','-d','--net=host','--privileged','-v','/dev/net:/dev/net','quay.io/coreos/flannel:0.5.5'],stderr=open('/dev/null'),stdout=subprocess.PIPE)

  # get container id
  cid=pipe.stdout.read().strip()
  pipe.wait()

  # get flannel subnet settings
  pipe = subprocess.Popen(['sudo','docker','-H','unix:///var/run/docker-bootstrap.sock','exec',format(cid),'cat','/run/flannel/subnet.env'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err = pipe.communicate()
  result = out.decode()

  try:
    out
  except NameError:
    ctx.logger.error("Error getting and setting flannel subnet settings: " + str(err))
  else:
    ctx.logger.info("Got flannel subnet successfully: " + str(result))

  flannel=";".join(result.split())
  # edit docker config
  edit_docker_config(flannel)

  # remove existing docker bridge
  os.system("sudo /sbin/ifconfig docker0 down")
  os.system("sudo apt-get install -y bridge-utils")
  os.system("sudo brctl delbr docker0")

  # restart docker
  os.system("sudo service docker start")

  # start the master
  subprocess.call("sudo docker run \
    --volume=/:/rootfs:ro \
    --volume=/sys:/sys:ro \
    --volume=/var/lib/docker/:/var/lib/docker:rw \
    --volume=/var/lib/kubelet/:/var/lib/kubelet:rw \
    --volume=/var/run:/var/run:rw \
    --net=host \
    --privileged=true \
    --pid=host \
    -d \
    gcr.io/google_containers/hyperkube-amd64:v1.2.3 \
    /hyperkube kubelet \
        --allow-privileged=true \
        --api-servers=http://localhost:{} \
        --v=2 \
        --address=0.0.0.0 \
        --enable-server \
        --hostname-override=127.0.0.1 \
        --config=/etc/kubernetes/manifests-multi \
        --containerized \
        --cluster-dns=10.0.0.10 \
        --cluster-domain=cluster.local".format(master_port), shell=True)

  # run the proxy
  # subprocess.call("sudo docker run -d --net=host --privileged gcr.io/google_containers/hyperkube:v1.0.1 /hyperkube proxy --master=http://127.0.0.1:{} --v=2".format(master_port),shell=True)

  # get kubectl
  subprocess.call("wget http://storage.googleapis.com/kubernetes-release/release/v1.2.3/bin/linux/amd64/kubectl", shell=True)
  subprocess.call("chmod 755 kubectl", shell=True)
