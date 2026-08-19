## Kubernetes

### Verify etcd member status

```bash
➜  ~ etcdctl --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/ssl/etcd/ssl/ca.pem \
  --cert=/etc/ssl/etcd/ssl/admin-$(hostname).pem \
  --key=/etc/ssl/etcd/ssl/admin-$(hostname)-key.pem member list
```

Example output:

```bash
44d62f51ecc7ca59, started, etcd1, https://172.20.0.1:2380, https://172.20.0.1:2379, false
7eb2d8d135c3acff, started, etcd3, https://172.20.0.3:2380, https://172.20.0.3:2379, false
a3d5ccda0e1528f7, started, etcd2, https://172.20.0.2:2380, https://172.20.0.2:2379, false
```

```bash
etcdctl --endpoints=https://172.20.0.1:2379,https://172.20.0.2:2379,https://172.20.0.3:2379 \
  --cacert=/etc/ssl/etcd/ssl/ca.pem \
  --cert=/etc/ssl/etcd/ssl/admin-$(hostname).pem \
  --key=/etc/ssl/etcd/ssl/admin-$(hostname)-key.pem \
  endpoint health --cluster
  ```

Example output:
```
{"level":"warn","ts":"2026-03-21T15:15:00.184013+0100","logger":"client","caller":"v3@v3.5.26/retry_interceptor.go:63","msg":"retrying of unary invoker failed","target":"etcd-endpoints://0xc00036a780/172.20.0.2:2379","attempt":0,"error":"rpc error: code = DeadlineExceeded desc = context deadline exceeded while waiting for connections to become ready"}
https://172.20.0.1:2379 is healthy: successfully committed proposal: took = 9.295218ms
https://172.20.0.3:2379 is healthy: successfully committed proposal: took = 11.523396ms
https://172.20.0.2:2379 is unhealthy: failed to commit proposal: context deadline exceeded
```

### Verify Cilium status

```bash
kubectl -n kube-system exec ds/cilium -- cilium status
```

Look for the entry `Cluster health`.

### Cilium Envoy fails to start with "unable to bind domain socket" / errno=98

If the `cilium-envoy` pod is crashing with logs like:
```text
unable to bind domain socket with base_id=0, id=0, errno=98 (see --base-id option)
```
This is likely because a ghosting/orphan Envoy instance is still running on the host and bound to the same socket. To fix this, SSH into the affected node and terminate the stray process:
```bash
ps aux | grep envoy
kill -9 <PID>
```

### CloudNativePG (CNPG) Replica Pod CrashLoopBackOff (`pg_controldata` failure / Corrupt Volume)

If a CNPG DB replica pod is crashing on a node with `pg_controldata` errors (or corrupt `pg_control` file / missing `pgdata` folder):

1. **Why PVC deletion alone doesn't re-bind**:
   The static PV (`local-pv-<node>-<cluster>`) has `persistentVolumeReclaimPolicy: Retain`. When the PVC is deleted, the PV moves to `Released` status and retains its `spec.claimRef`. Kubernetes will not bind a new PVC until the `claimRef` is cleared (or the PV is recreated) and the host directory `/app/k8s-db-<cluster>` is cleaned.

2. **Clean-up & Restore Procedure**:
   - Delete the failing Pod and PVC:
     ```bash
     kubectl delete pod -n <namespace> <pod-name>
     kubectl delete pvc -n <namespace> <pvc-name>
     ```
   - Wipe the local host storage path on the target node (e.g. `node3`):
     ```bash
     sudo rm -rf /app/k8s-db-<cluster>/*
     ```
   - Release the PV by clearing its `claimRef`:
     ```bash
     kubectl patch pv local-pv-<node>-<cluster> -p '{"spec":{"claimRef":null}}'
     ```
   - Alternatively, delete the PV (`kubectl delete pv local-pv-<node>-<cluster>`) and re-apply the Ansible role:
     ```bash
     ansible-playbook -i inventory/home.yaml install_kubernetes.yaml --tags k8s-db
     ```
   CNPG will automatically create a new PVC, bind the `Available` PV, and stream a fresh replica sync from the primary database instance.

---

## DRBD & Linstor (Piraeus Datastore)

This section explains how to inspect, troubleshoot, and validate your Piraeus Datastore (Linstor/DRBD) deployment. Since Piraeus runs as a Kubernetes-native storage solution, interacting with it involves a combination of **host-level checks** (LVM, loopbacks, kernel states) and **Kubernetes commands** (Linstor CLI).

### 1. Host-Level Validation & Troubleshooting

Since Linstor Satellites configure storage resources directly on the host kernel, you can inspect the physical state of LVM and DRBD from your physical hosts (`node1`, `node2`, `node3`).

#### A. Verify Loopback Storage Status
To check if the persistent loopback backing file is correctly attached to `/dev/loop100`:
```bash
# Verify loopback service is active
systemctl status linstor-loopback

# View all active loop devices
losetup -a

# Specifically check loop100
losetup /dev/loop100
```

#### B. Verify LVM & Thin Pool Status
To verify that the LVM volume group and thin pool are created and healthy:
```bash
# Check Volume Groups (should list linstor_vg)
sudo vgs

# Check Logical Volumes (should list thin_pool and its allocation percentage)
sudo lvs

# Get detailed information on the thin pool
sudo lvdisplay linstor_vg/thin_pool
```

#### C. Verify DRBD Kernel Status
DRBD operates inside the host kernel space, but in a Kubernetes-native Piraeus environment, the user-space CLI tools (`drbdsetup`, `drbdmon`, `drbdadm`) are **packaged inside the container images** and run within the `linstor-satellite` pods rather than on the bare host system.

Because the Linstor satellite containers run in **privileged** mode and share the host's kernel namespaces (`/sys`, `/proc`, `/dev`), running these commands inside the pods interacts directly with the host's active DRBD kernel module. **You do not need to install `drbd-utils` on your host nodes.**

##### Option 1: Running via Kubernetes Satellites (Recommended)
You can run these commands inside the satellite pod running on the target node:
```bash
# 1. Identify the satellite pod name running on your target node (e.g., node1)
kubectl get pods -n piraeus-datastore -o wide -l app.kubernetes.io/component=linstor-satellite

# 2. Exec into the pod to view DRBD status or active console
kubectl exec -it -n piraeus-datastore linstor-satellite-xxxxx -- drbdsetup status
kubectl exec -it -n piraeus-datastore linstor-satellite-xxxxx -- drbdmon
```

##### Option 2: Running directly on Host (Optional)
If you prefer running these commands directly on the host prompt without `kubectl`, you can optionally install the utility packages on your physical nodes:
```bash
# On Ubuntu/Debian hosts:
sudo apt-get update && sudo apt-get install -y drbd-utils

# Then you can run them directly:
sudo drbdsetup status
sudo drbdmon
```

In both cases, you can view the kernel logs directly from the host system:
```bash
# Check host kernel logs for any DRBD connection or sync errors
dmesg | grep -i drbd
```

---

### 2. Kubernetes-Native Validation & CLI Interaction

The Linstor controller holds the master state of your cluster. Since it is running inside the Kubernetes cluster, you can run Linstor CLI commands using `kubectl exec`.

#### A. Accessing the Linstor CLI
Run all standard Linstor administrative commands through the controller deployment:
```bash
# Get cluster nodes status (should show all three nodes as ONLINE)
kubectl exec -it -n piraeus-datastore deploy/linstor-controller -- linstor node list

# List all storage pools (should list thin-pool on all nodes as healthy)
kubectl exec -it -n piraeus-datastore deploy/linstor-controller -- linstor storage-pool list

# View configured volume definitions
kubectl exec -it -n piraeus-datastore deploy/linstor-controller -- linstor volume-definition list

# View active resources (sync status, primary/secondary states)
kubectl exec -it -n piraeus-datastore deploy/linstor-controller -- linstor resource list

# View detailed volume placements and devices
kubectl exec -it -n piraeus-datastore deploy/linstor-controller -- linstor volume list
```

#### B. Accessing the Satellite Controllers
To check logs or inspect a specific node's Linstor satellite daemon:
```bash
# Get running satellite pods
kubectl get pods -n piraeus-datastore -l app.kubernetes.io/component=linstor-satellite

# Follow logs on a specific satellite node
kubectl logs -n piraeus-datastore linstor-satellite-xxxxx
```

---

### 3. Common Troubleshooting Scenarios

#### A. Split-Brain Recovery
If a network disconnect occurs and both nodes write independently, DRBD will flag a split-brain state to protect your data from corruption. Linstor will mark the resource as **Unconfigured** or **Inconsistent**.

To inspect split-brain details:
```bash
kubectl exec -it -n piraeus-datastore deploy/linstor-controller -- linstor resource list
```
*To resolve a split-brain, you typically have to choose one node as the survivor (discarding modifications on the other node).* Linstor simplifies this:
```bash
# Force one node's resource to become the secondary target to sync from the correct source
kubectl exec -it -n piraeus-datastore deploy/linstor-controller -- linstor resource connection disconnect <node-a> <node-b>
```

#### B. Recreating Storage Pools
If you ever need to manually delete and recreate a satellite's storage pool configuration inside Linstor:
```bash
# Delete the pool configuration from Linstor
kubectl exec -it -n piraeus-datastore deploy/linstor-controller -- linstor storage-pool delete <node-name> thin-pool

# Re-register the pool
kubectl exec -it -n piraeus-datastore deploy/linstor-controller -- linstor storage-pool create lvmthin <node-name> thin-pool linstor_vg thin_pool
```

#### C. Linstor Satellite Disconnect & Lost Quorum Taints (`drbd.linbit.com/lost-quorum`)
If a storage satellite fails to attach its backing loopback storage or loses connectivity to the Linstor controller:
1. `linstor node list` will report the satellite as `OFFLINE`.
2. Pods requiring storage volume mounts will fail to start (`FailedAttachVolume: ControllerPublishVolume failed ... could not determine device path`).
3. Linstor will automatically apply `drbd.linbit.com/lost-quorum` `NoSchedule` taints on affected nodes, preventing pod scheduling (`0/3 nodes available ... had untolerated taint(s)`).

**Recovery Steps:**
1. Verify the `linstor-loopback` service is active on the physical host:
   ```bash
   systemctl status linstor-loopback
   ```
2. Restart the `linstor-satellite` pod on the affected node to trigger satellite re-registration:
   ```bash
   kubectl delete pod -n piraeus-datastore -l app.kubernetes.io/instance=linstor-satellite.<node-name>
   ```
3. Verify that `linstor node list` returns `Online` or `Connected`:
   ```bash
   kubectl exec -it -n piraeus-datastore deploy/linstor-controller -- linstor node list
   ```
4. Remove any stale `drbd.linbit.com/lost-quorum` taints from affected nodes:
   ```bash
   kubectl taint nodes <node-name> drbd.linbit.com/lost-quorum-
   ```

---

### 4. Storage Architecture FAQ & Verification Guide

#### A. Does deleting a PVC release physical storage space in Linstor?
**Yes!** By default, our StorageClasses use `reclaimPolicy: Delete`.
When you delete a PVC:
1. Kubernetes tells the Linstor CSI driver to destroy the volume.
2. Linstor deletes the LVM Thin logical volume representing the block storage on the node.
3. Because we use **LVM Thin Provisioning**, deleting a Thin Logical Volume instantly releases the physical allocated sectors inside the shared `linstor_vg/thin_pool`, immediately making that space available for other volumes.

#### B. What happens if a Pod is scheduled on a node that does not have a local replica?
It still works perfectly, thanks to **DRBD Diskless Mode**!
If `placementCount: "2"` placed active replicas on `node1` and `node2`, but the pod gets scheduled on `node3`:
1. The Linstor CSI driver automatically instantiates a local **diskless DRBD device** on `node3`.
2. DRBD transparently redirects all read and write block operations over the network (using DRBD's transport layer) to the storage replicas on `node1` and `node2`.
3. The pod accesses `/dev/drbdX` as if it were local, fully unaware that the blocks are traveling across nodes.
*Note: To optimize performance, our StorageClasses configure `volumeBindingMode: WaitForFirstConsumer`, which helps the Kubernetes scheduler align pod placement with storage nodes to prioritize data locality whenever possible.*

---

## Kubelet Storage Partitioning & Bind-Mount Architecture

### Storage Layout Across Nodes

In this homelab cluster, the storage partitioning differs between nodes:

- **`node1` & `node3`**: Configured with a single large root partition (~470GB), with ample space (>370GB free). `/var/lib/kubelet` resides directly on `/`.
- **`node2`**: Configured with a split LVM layout consisting of a small 50GB root logical volume (`system--vg-system--lv`) and a large 750GB application logical volume (`system--vg-app--lv` mounted at `/app`).

### Why Bind Mount (`/app/kubelet` $\rightarrow$ `/var/lib/kubelet`)?

Attempting to change Kubelet's root directory via `--root-dir=/app/kubelet` causes path misalignment with CSI drivers (such as Piraeus/Linstor) and standard Kubernetes controllers which default to and expect socket registration under `/var/lib/kubelet/plugins*`.

By using an **`/etc/fstab` bind mount**:
1. All physical data (ephemeral pod volumes, CSI volume links, plugins) is stored on the large `/app` filesystem.
2. Kubernetes, Kubelet, and CSI plugins interact seamlessly with the standard `/var/lib/kubelet` path without requiring custom DaemonSet volume overrides or patched CSI registration arguments.
3. Ansible configuration stays simple: `kubelet_mount_src: "/app/kubelet"` in `home.yaml` manages the creation and fstab entry via `install_kubernetes.yaml`.

### Step-by-Step Node Migration Procedure

If a node with a small root partition needs to be migrated to use `/app/kubelet`:

1. **Drain the node** (from control-plane):
   ```bash
   sudo KUBECONFIG=/etc/kubernetes/admin.conf kubectl drain <node> --ignore-daemonsets --delete-emptydir-data --force
   ```

2. **Stop services on the target node**:
   ```bash
   systemctl stop kubelet containerd
   ```

3. **Unmount active pod volumes & sync data**:
   ```bash
   # Unmount lingering mounts
   mount | grep /var/lib/kubelet | awk '{print $3}' | sort -r | xargs -r umount

   # Ensure destination directory exists
   mkdir -p /app/kubelet
   chmod 750 /app/kubelet

   # Sync existing data
   rsync -aHAXSP --delete /var/lib/kubelet/ /app/kubelet/

   # Backup old directory and create mountpoint
   mv /var/lib/kubelet /var/lib/kubelet.bak
   mkdir -p /var/lib/kubelet
   chmod 755 /var/lib/kubelet
   ```

4. **Configure `/etc/fstab` & mount**:
   ```bash
   echo '/app/kubelet /var/lib/kubelet none defaults,bind 0 0' >> /etc/fstab
   mount -a
   findmnt /var/lib/kubelet
   ```

5. **Start services (or reboot to test persistence)**:
   ```bash
   systemctl daemon-reload
   systemctl start containerd kubelet
   # or: reboot
   ```

6. **Uncordon the node and verify**:
   ```bash
   sudo KUBECONFIG=/etc/kubernetes/admin.conf kubectl uncordon <node>
   sudo KUBECONFIG=/etc/kubernetes/admin.conf kubectl get nodes -o wide
   sudo KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -n piraeus-datastore -o wide
   ```

7. **Clean up backup**:
   ```bash
   rm -rf /var/lib/kubelet.bak
   ```

8. **Update Ansible Inventory**:
   Add `kubelet_mount_src: "/app/kubelet"` under the host in [ansible/inventory/home.yaml](ansible/inventory/home.yaml).
