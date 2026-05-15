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

### Verify Cilium status

```bash
kubectl -n kube-system exec ds/cilium -- cilium status
```

Look for the entry `Cluster health`.