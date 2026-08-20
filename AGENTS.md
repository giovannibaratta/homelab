Never execute write command on this local host of the remote host. This inlucdes ssh commands, or proxying to the hosts via Ansible.

You can inspect the hosts (not the local one) using the availabe skills 'ansible-nodes'.

This is the ansible repository to manager the remote hosts.

There is a mix of containers and pods running in Podman and Kubernetes.

Do not start and run 30/40s commands without reporting back to the user once in a while with the current summary of your discoveries and hypothesis.

Some of the already known issues are documented in troubleshooting.md. This document should be updated when new failures are identified.

## Ansible Deploy / Undeploy Architecture Pattern

When creating or modifying Ansible roles managing services/containers:

1. **Role Import in Playbooks**:
   Do not gate top-level `import_role` calls with coarse `when: deploy_<role>` conditions in playbooks (`setup_homelab.yaml`). The role must execute on all runs to evaluate per-host lifecycle cleanup.

2. **Role Entrypoint (`main.yml`)**:
   Calculate summary facts (e.g. `__<service>_any_enabled`) once at top of `main.yml`, then import deploy and undeploy files sequentially:
   ```yaml
   - name: Determine if any component is enabled
     ansible.builtin.set_fact:
       __<service>_any_enabled: "{{ (deploy_comp_a | default(false) | bool) or (deploy_comp_b | default(false) | bool) }}"

   - name: Deploy components
     ansible.builtin.import_tasks: deploy_<service>.yaml

   - name: Undeploy components
     ansible.builtin.import_tasks: undeploy_<service>.yaml
   ```

3. **Deploy File (`deploy_<service>.yaml`)**:
   Contains ONLY installation and start tasks. Gate each component block with:
   `when: deploy_<component> | bool`

4. **Undeploy File (`undeploy_<service>.yaml`)**:
   Contains ONLY stop, disable, and resource cleanup tasks (removing Quadlet `.container`/`.network` files and daemon-reloading). Gate each cleanup block with:
   `when: not (deploy_<component> | default(false) | bool)`

5. **Boolean Safety**:
   Always pipe boolean variables through `| bool` (e.g. `when: not (deploy_foo | default(false) | bool)`) to prevent Jinja string evaluation bugs (`"false"` string evaluating to truthy).

## Ingress & Traefik Security Middleware Pattern

When exposing any web service or creating/modifying Traefik routes:

1. **Do NOT apply global HTTP middlewares to the `public-secure` (:9443) entrypoint**:
   Entrypoint middlewares apply unconditionally to all traffic on that port. Streaming/gRPC services (e.g. Netbird) break under ModSecurity WAF deep inspection and need to share port 9443.

2. **Always enforce security middlewares at the router/endpoint level**:
   - **Default to the most secure**: Always use `default-chain@file` (rate limiting + concurrency control + ModSecurity WAF).
   - **Opt-out only when strictly needed**: Use alternative chains (e.g. rate limiting + concurrency control, bypassing WAF) only for services that break under deep packet inspection (e.g., VPN, gRPC, or streaming services).

3. **Kubernetes Ingress**:
   - Add new public Kubernetes domains to `k8s_public_domains` in `inventory/home.yaml`. `homelab.system.ingress` (`k8s-routing.yaml.j2`) will automatically generate the public Traefik routers with all 3 security layers.
   - Add internal-only Kubernetes domains to `k8s_internal_domains`.

4. **Podman / Container Services**:
   - When defining Quadlet container labels for exposed services, ALWAYS default to:
     `traefik.http.routers.<service_name>.middlewares: default-chain@file`