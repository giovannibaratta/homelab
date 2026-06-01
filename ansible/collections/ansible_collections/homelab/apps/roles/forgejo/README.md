# Forgejo Role Backups Guide

This guide explains how the local, credential-free backup system works for Forgejo, how to trigger a backup manually, and how to securely copy the backup bundles to your local machine using standard `kubectl` commands.

## How It Works
1. A daily Kubernetes `CronJob` (`forgejo-backup`) runs every day at 2:00 AM.
2. The backup script queries the Forgejo REST API using administrative credentials to locate all active Git repositories.
3. It performs a bare clone of each repository and creates a `.bundle` archive using `git bundle create`.
4. The `.bundle` files are written directly to a Kubernetes Persistent Volume Claim (`forgejo-backup-pvc`), keeping them local and secure within your cluster.

---

## 1. Trigger Backups Manually
If you want to create a backup immediately (e.g. before an upgrade or system maintenance), you can run a manual backup Job using the CronJob template.

Run the following command on your control plane or a workstation connected to the cluster:

```bash
kubectl create job --from=cronjob/forgejo-backup -n git-system forgejo-backup-manual
```

To watch the progress of the manual backup, track the pod's logs:
```bash
# Get the pod name
POD_NAME=$(kubectl get pods -n git-system -l job-name=forgejo-backup-manual -o jsonpath='{.items[0].metadata.name}')

# View logs
kubectl logs -n git-system -f $POD_NAME
```

## 2. Download Backups Locally
Because backup jobs exit and mark themselves as `Succeeded` immediately upon completion, you cannot run `kubectl cp` directly from a completed job pod (Kubernetes blocks exec/cp into non-running containers).

To download the repository backup `.bundle` files securely, spin up a temporary, PSS-compliant helper pod that mounts the backup PVC, copy the files, and delete the helper when done:

```bash
# 1. Create a local directory for your backups on your machine
mkdir -p ~/backups/forgejo

# 2. Spin up a temporary helper pod that mounts the backup PVC (runs for 5 minutes)
kubectl run backup-helper -n git-system --image=alpine/git:latest --restart=Never \
  --overrides='{"spec":{"securityContext":{"runAsNonRoot":true,"runAsUser":1000,"runAsGroup":1000,"fsGroup":1000,"seccompProfile":{"type":"RuntimeDefault"}},"containers":[{"name":"helper","image":"alpine/git:latest","command":["sleep","300"],"volumeMounts":[{"name":"vol","mountPath":"/backups"}],"securityContext":{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"runAsNonRoot":true,"runAsUser":1000,"runAsGroup":1000,"seccompProfile":{"type":"RuntimeDefault"}}}],"volumes":[{"name":"vol","persistentVolumeClaim":{"claimName":"forgejo-backup-pvc"}}]}}'

# 3. Copy the backup bundles to your local machine
kubectl cp -n git-system backup-helper:/backups ~/backups/forgejo/

# 4. Clean up the helper pod
kubectl delete pod -n git-system backup-helper
```

Once you have successfully downloaded the backups, you can also delete the manual backup job from the cluster:
```bash
kubectl delete job -n git-system forgejo-backup-manual
```

---

## 3. How to Restore/Unbundle a Backup
A Git bundle is a highly elegant, self-contained single-file representation of a full Git repository (with all commits, history, and branches).

To restore or unbundle the `.bundle` file back into an active local Git repository:

### Option A: Clone the Bundle (Recommended)
You can treat the `.bundle` file exactly like a remote Git repository URL. Running `git clone` on the bundle file creates a fully initialized working directory with all repository history intact:

```bash
# Clone the bundle into a directory named 'tax-return-ai'
git clone tax-return-ai.git-2026-06-01.bundle tax-return-ai
```

### Option B: Verify the Bundle Contents
If you want to check what branches and references are contained inside the bundle before restoring it, run:
```bash
git bundle verify tax-return-ai.git-2026-06-01.bundle
```

### Option C: Fetch from the Bundle into an Existing Repo
If you have an existing repository and want to pull the latest commits directly from the bundle file, treat the bundle file as the remote:
```bash
# Fetch from the bundle file directly into your local main branch
git fetch tax-return-ai.git-2026-06-01.bundle main:main
```
