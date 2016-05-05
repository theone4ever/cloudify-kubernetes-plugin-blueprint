## Cloudify Kubernetes Plugin

This project contains sample blueprints that demonstrate a hybrid cloud scenario involving microservice and non-microservice orchestration, along with Cloudify driven microservice autoscaling in Kubernetes.  The details of that sample are [here](#hybrid-cloud-example).

Limitations (as of 5/2/2016):
+ Only tested on Ubuntu 14
+ Tested on Openstack Helion and Kilo
+ Tested on Cloudify 3.2.1 and 3.3.1

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

In the log, note the "conns=1.0" value.  This is the value that will trigger scaling if it gets larger than 2.  The number of "conns" (connections) is the average over a 10 second sliding window.  Start tailing the log in one window (e.g. `tail -f riemann.log`), and open another on the Kubernetes master.  Now we want to hammer the app with traffic.  You'll need the "ab" tool (`sudo apt-get install -y apache2-utils`).  This should do:

```bash
ab -n 10 -c 10 -t 10 http://localhost:30000/
```

That should put the connections over 2 and you'll see an entry in the log that says `SCALE`.  Now on the master run `./kubectl get rc`, and you'll see something like:

```
CONTROLLER   CONTAINER(S)   IMAGE(S)                SELECTOR         REPLICAS
nodecellar   nodecellar     dfilppi/nodecellar:v2   app=nodecellar   2
             diamondd       dfilppi/diamond:v1

```

