# Validate shared inventory

Call this role before managing cluster resources:

```yaml
- name: Validate shared settings
  ansible.builtin.include_role:
    name: homelab.system.validate_shared_inventory
  vars:
    shared_inventory_variables:
      - deploy_seerr
```

Each listed variable must be explicitly available on every host in `groups['all']`
and have the same value and type. Checks include hosts excluded by `--limit`.
Failures identify variable and host names without printing values.