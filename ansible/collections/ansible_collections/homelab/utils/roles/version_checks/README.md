# Controller version checks

This role checks the Ansible controller's dependencies before deployment and
stops with a clear error when an installed version is incompatible. It does not
install or upgrade dependencies.

## Requirements checked

| Dependency | Accepted versions | When checked |
| --- | --- | --- |
| Ansible core | `>=2.19,<2.20` | Every run, including tagged runs |
| `prometheus.prometheus` collection | `>=0.29.0,<0.30.0` | Full runs and runs selecting the `prometheus` tag |

The Prometheus collection is required for host exporters as well as the
Prometheus server. Its check therefore applies even to hosts that do not deploy
the server. Skipping the `prometheus` tag skips that check.

## Usage

Import the role once in the playbook's pre-tasks:

```yaml
pre_tasks:
  - name: Check controller dependencies
    ansible.builtin.import_role:
      name: homelab.utils.version_checks
    run_once: true
```

To check only Ansible core, add `tasks_from: ansible.yaml` to the role import.
Keep task-level tags intact so checks follow the selected deployment scope.

There are no configuration variables. Install the repository's declared
requirements in the active controller environment when a check fails, then
rerun the playbook.
