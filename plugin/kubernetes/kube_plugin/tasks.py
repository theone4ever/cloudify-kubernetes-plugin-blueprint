########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

#
# Kubernetes plugin implementation
#
from cloudify.decorators import operation
from cloudify import ctx,manager
import os
import re
import time
import subprocess
import yaml

# Called when connecting to master.  Gets ip and port
@operation
def connect_master(**kwargs):
  if(ctx._local):
    ctx.source.instance.runtime_properties['master_ip']=ctx.target.node.properties['ip']
  else:
    ctx.source.instance.runtime_properties['master_ip']=ctx.target.instance.runtime_properties['ip']
    ctx.source.instance.runtime_properties['master_port']=ctx.target.node.properties['master_port']
    ctx.source.instance.runtime_properties['ssh_username']=ctx.target.node.properties['ssh_username']
    ctx.source.instance.runtime_properties['ssh_password']=ctx.target.node.properties['ssh_password']
    ctx.source.instance.runtime_properties['ssh_port']=ctx.target.node.properties['ssh_port']
    ctx.source.instance.runtime_properties['ssh_keyfilename']=ctx.target.node.properties['ssh_keyfilename']

@operation
def contained_in(**kwargs):
  ctx.source.instance.runtime_properties['ip']=ctx.target.instance.runtime_properties['ip']

@operation
def copy_rtprops(**kwargs):
  if (not "prop_list" in kwargs or kwargs["prop_list"]==""):
    return
  for prop in kwargs['prop_list'].split(','):
    if(prop in ctx.target.instance.runtime_properties):
      ctx.source.instance.runtime_properties[prop]=ctx.target.instance.runtime_properties[prop]
    
def process_subs(s):
  client=None
  m=re.search('@{([^,}]*),([^}]*)}',s)
  while(m):
    if m and len(m.groups())==2:
      # do substitution
      if(not client):
        ctx.logger.info("creating client")
        client=manager.get_rest_client()
      instances=client.node_instances.list(deployment_id=ctx.deployment.id,node_name=m.group(1))
      ctx.logger.info("got instances {}".format(instances))
      if(instances and len(instances)):
        #just use first if more than one
        val=instances[0].runtime_properties[m.group(2)]
        ctx.logger.info("val to sub={}".format(val))
        s=s[:m.start(0)]+val+s[m.end(2)+1:]
        ctx.logger.info("sub result={}".format(s))
        m=re.search('@{([^,}]*),([^}]*)}',s)
      else:
        raise Exception("no instances found for node: {}".format(m.group(1)))
    else:
      raise Exception("invalid pattern: "+s)
  return s

@operation
def kube_run_expose(**kwargs):
  config=ctx.node.properties['config']
  config_path=ctx.node.properties['config_path']
  config_overrides=ctx.node.properties['config_overrides']

  def write_and_run(d):
    os.chdir(os.path.expanduser("~"))
    fname="/tmp/kub_{}.yaml".format(ctx.instance.id)
    with open(fname,'w') as f:
      yaml.safe_dump(d,f)
    cmd="./kubectl -s http://localhost:8080 create -f "+fname + " >> /tmp/kubectl.out 2>&1"
    ctx.logger.info("running create: {}".format(cmd))

    #retry a few times
    retry=0
    while subprocess.call(cmd,shell=True):
      if retry>3:
        raise Exception("couldn't connect to server on 8080")
      retry=retry+1
      ctx.logger.info("run failed retrying")
      time.sleep(2)

  if(config):
    write_and_run(config)
  elif(config_path):
    if (not ctx._local):
      config_path=ctx.download_resource(config_path)
    with open(config_path) as f:
      base=yaml.load(f)
    if(config_overrides):
      for o in config_overrides:
        ctx.logger.info("exeing o={}".format(o))
        #check for substitutions
        o=process_subs(o)
        exec "base"+o in globals(),locals()
    write_and_run(base)
  else:
    # do kubectl run
    cmd='./kubectl -s http://localhost:8080 run {} --image={} --port={} --replicas={}'.format(ctx.node.properties['name'],ctx.node.properties['image'],ctx.node.properties['target_port'],ctx.node.properties['replicas'])
    if(ctx.node.properties['run_overrides']):
      cmd=cmd+" --overrides={}".format(ctx.node.properties['run_overrides'])

    subprocess.call(cmd,True)

    # do kubectl expose
    cmd='./kubectl -s http://localhost:8080 expose rc {} --port={} --protocol={}'.format(ctx.node.properties['name'],ctx.node.properties['port'],ctx.node.properties['protocol'])
    if(ctx.node.properties['expose_overrides']):
      cmd=cmd+" --overrides={}".format(ctx.node.properties['expose_overrides'])

    subprocess.call(cmd,shell=True)
