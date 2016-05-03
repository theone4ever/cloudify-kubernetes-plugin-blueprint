## Cloudify Kubernetes Plugin

This project contains a plugin that enables Cloudify to install, configure, and run services on a Kubernetes cluster. It also includes sample blueprints that demonstrate a hybrid cloud scenario involving microservice and non-microservice orchestration, along with Cloudify driven microservice autoscaling in Kubernetes.  The details of that sample are [here](#hybrid-cloud-example).

Limitations (as of 5/2/2016):
+ Only tested on Ubuntu 14
+ Tested on Openstack Helion and Kilo
+ Tested on Cloudify 3.2.1 and 3.3.1

### Plugin components

#### cloudify.kubernetes.Master node type

Represents a Kuberenets master node.  This is the only essential node in the plugin.  All other node types and workflows require a master node to be defined.  By default, it will install Kubernetes to the identified host, but it can be configured to merely connect to an existing master.  If desired, the blueprint will also install docker if the `install_docker` property is `true`.

<b>Interesting properties</b>
+ install_agent      boolean (default=false) that determines whether to install a Cloudify agent on the target host.
+ install_docker     boolean (default=false) that determines whether the plugin will install docker before attempting to install Kuberenets
+ install            boolean (default=true) that determines whether the plugin will install Kubernetes itself.  If `false`, it will simply connect
+ master_port        int (default 8080) that indicates where Kubernetes will listen for requests 

#### cloudify.kubernetes.Node node type

Represents a Kubernetes "node" or "minion".  Unused if simply connecting to an existing cluster.  Extracts connection information to the master via the [`cloudify.kubernetes.relationships.connected_to_master`](#conn-to-master) relationship.

#### cloudify.kubernetes.MicroService type

Represents a "microservice" in a Kubernetes cluster.  Requires the [`cloudify.kubernetes.relationships.connected_to_master`](#conn-to-master) relationship to get connection information.  Can define a service by plugin properties, by embedded Kubernetes native YAML, and by referring to a standard Kubernetes YAML deployment manifest while permitting overrides.  When using either form of native YAML, the actual Kubernetes action performed is determined by the configuration, which means that in reality it may or may not actually create a Kubernetes service, replication control, or other artifact.  Actual command execution on Kubernetes is performed by the [fabric plugin](https://github.com/cloudify-cosmo/cloudify-fabric-plugin) by remotely executing the Kubernetes `kubectl` executable on the master node.

<b>Interesting properties</b>
<li> non-native service definition - uses kubectl on master to first run a "run" command, followed by an "expose" command.

 Property        | Description                                   
 --------------- |  ---------------------
 name            | service name                                  
 image           | image name                                    
 port            | service listening port                        
 target_port     | container port (default:port)                 
 protocol        | TCP/UDP  (default TCP)                        
 replicas        | number of replicas (default 1)                   
 run_overrides   | json overrides for kubectl "run"              
 expose_overrides| json overrides for kubectl "expose"          

<nbsp>
<li>native embedded properties

 Property        | Description                                 
 --------------- | ---------------------------------------------
 config          | indented children are native Kubernetes YAML

<nbsp>
<li>native file reference properties

 Property        | Description                                
 --------------- | ---------------------------------------------
 config_path     | path to Kubernetes manifest               
 config_overrides| replacement values for external manifest 


#### cloudify.kubernetes.relationships.connected_to_master relationship <a id="#conn-to-master"></a>

Just retrieves the master ip and port for use by the dependent node.

#### "Generic" Workflows

With the exception of the `kube_scale` workflow (covered below), these workflows just delegate to `kubectl` on the master.  They all share a parameter called `master`.  The `master` parameter is set to the node name of the Kubernetes master that the workflow is to be run against.  Another pattern is to provide many (but not all) of the parameters that `kubectl` accepts, but using the `overrides` property as a catch all.
These workflows are provided as samples.  It should be understood that any actual producion blueprint would only implement workflows relevant to the blueprint purpose, which may or may not include the following, and probably contain others.

Workflow name| Description
------ | -------
kube_run         | `kubectl run` equivalent
kube_expose      | `kubectl run` equivalent
kube_stop        | `kubectl stop` equivalent
kube_delete      | `kubectl delete` equivalent

#### The "kube_scale" Workflows

The function of `kube_scale` is not to scale Kubernetes minion/node servers.  Scaling Kubernetes is handled by the standard `scale` workflow in Cloudify.  `kube_scale` scales deployed Microservices.  The amount of scale can be supplied as either an fixed number (e.g. 5) or an increment (e.g. +2 or -1).  The parameters are as follows:

Parameter | Description
------- | --------
master             | the master node in the blueprint.  Can be a standard node or a deployment proxy.
ssh_user           | the user that Kubernetes was installed as
ssh_keyfilename    | the key file name for the ssh_user
name               | the name of the Microservice node
amount             | the scale value (e.g. 2), or the scale increment (e.g. "+1).

## Hybrid Cloud Example

The hybrid cloud example can be found in the `openstack-proxy-blueprint` directory.  As the name implies, the blueprints target openstack (tested on Helion and Kilo), and most recently tested on Cloudify 3.3.1.  The example demonstrates three separate blueprints that are orchestrated together by using the Cloudify deployment proxy type (available [separately](https://github.com/cloudify-examples/cloudify-proxy-plugin) on github).  The blueprints together are another twist on the familiar Nodecellar [example](https://github.com/cloudify-cosmo/cloudify-nodecellar-example).  In this case, Nodejs is deployed as a Kubernetes microservice, that connects to an external (to Kubernetes) instance of MongoDb.  Additionally, a policy is defined to demonstrate a simple microservice autoscaling scenario.  

### Installation Instructions

1. In the `inputs` directory are 3 inputs files, one for each of the blueprints.  The "kub" inputs are the same as the "mongo" inputs, but you can vary them if you like (except for the `ubuntu` user).  The "hybrid" inputs are simply the names you will assign to the deployments you will create for Kubernetes and MongoDb (e.g. kub-deployment and mongo-deployment).  These blueprints have only been tested on Ubuntu 14.04 and up, so use a 14.04 image.  As always with Cloudify, any image you use must support passwordless ssh, and passwordless sudo (including from an ssh client).  Otherwise agent installation will fail.
2. Start Kubernetes.
2.1 `cfy blueprints upload -p openstack-kubonly-blueprint -b kub-blueprint`
2.2 `cfy deployments create -b kub-blueprint -d kub-deployment -i os-inputs-kub.yaml`
2.3 `cfy executions start -d kub-deployment -w install
2.4  Verify it worked.  ssh to the manager and then to the Kubernetes master node.  You should be able to run `./kubectl get pods` and see the kubelet running (no errors).

3. Start MongoDb.
3.1 `cfy blueprints upload -p openstack-mongo-blueprint -b mongo-blueprint`
3.2 `cfy deployments create -b openstack-mongo-blueprint -d mongo-deployment -i os-inputs-mongo.yaml`
3.3 `cfy executions start -d mongo-deployment -w install

4. Install the Microservice
4.1 `cfy blueprints upload -p openstack-hybridservices-blueprint -b mongo-blueprint`
4.2 `cfy deployments create -b openstack-hybridservices-blueprint -d hybridservices-deployment -i os-inputs-hybrid.yaml`
4.3 `cfy executions start -d hybridservices-deployment -w install

### Validation/Operation Instructions

At this point, Kubernetes should be serving Nodecellar from the external MongoDb.  Open a browser to `http://<kub-master-ip>:30000/` and you should see the Nodecellar page.  

You can ssh to the Kubernetes master node and run `./kubectl get svc` and you should see:

`nodecellar-service   <none>                                    app=nodecellar   10.0.0.37   8888/TCP`

Run `./kubctl get rc` and you should see this:

```
CONTROLLER   CONTAINER(S)   IMAGE(S)                SELECTOR         REPLICAS
nodecellar   nodecellar     dfilppi/nodecellar:v2   app=nodecellar   1
             diamondd       dfilppi/diamond:v1
```

Note the number of replicas is 1.  To see the autoscaling work, ssh to the Cloudify manager and tail the Riemann log file at `/var/log/cloudify/riemann/riemann.log`.  You'll see something like:

```
INFO [2016-05-02 23:30:54,794] pool-2-thread-6 - riemann.config - cooling= false  scale_direction=< hostcnt= 1  scale_threshold=2 conns= 1.0
INFO [2016-05-02 23:30:59,792] pool-2-thread-4 - riemann.config - got event:  {:path connections, :service hd.nodecellar.nodecellar_407ea..connections, :unit , :name , :time 1462231859, :node_id nodecellar_407ea, :type GAUGE, :host 10_1_61_2, :ttl 10.0, :node_name nodecellar, :deployment_id hd, :metric 1.0}
INFO [2016-05-02 23:30:59,792] pool-2-thread-4 - riemann.config - cooling= false  scale_direction=< hostcnt= 1  scale_threshold=2 conns= 1.0

```

In the log, note the "conns=1.0" value.  This is the value that will trigger scaling if it gets larger than 2.  The number of "conns" (connections) is the average over a 10 second sliding window.  Start tailing the log in one window (e.g. `tail -f riemann.log`), and open another on the Kubernetes master.  Now we want to hammer the app with traffic.  This should do:

```bash
for i in `seq 1500`;do
   curl localhost:3000 >/dev/null 2>&1 &
done
```

That should put the connections over 2 and you'll see an entry in the log that says `SCALE`.  Now on the master run `./kubectl get rc`, and you'll see something like:

```
ONTROLLER   CONTAINER(S)   IMAGE(S)                SELECTOR         REPLICAS
nodecellar   nodecellar     dfilppi/nodecellar:v2   app=nodecellar   2
             diamondd       dfilppi/diamond:v1

```

