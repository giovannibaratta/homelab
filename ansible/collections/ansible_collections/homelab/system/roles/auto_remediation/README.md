# Automatic Ansible runs

This role prepares a host to periodically apply its homelab configuration from
the repository's `main` branch. It installs the runner and its dependencies,
configures access to Bitwarden Secrets Manager, and creates a scheduled job.
Normal runs export metrics for monitoring their results.

Scheduled execution is disabled by default. The runner can also be invoked
manually to test selected roles or a development branch.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `auto_ansible_enabled` | Enable the scheduled job | `false` |
| `auto_ansible_hour_schedule` | Hours to run, using cron syntax | `"*/4"` |
| `auto_remediation_bws_access_token` | Bitwarden Secrets Manager access token | Required |

The job runs at minute 30 of the selected hours, using the host's local time.
For example, to run once a day at 03:30:

```yaml
auto_ansible_enabled: true
auto_ansible_hour_schedule: "3"
```

Supply the access token through your secret-management configuration. Setting
`auto_ansible_enabled: false` disables the scheduled job; manual runs remain
available.

## Manual runs

Run the installed command on the host:

```sh
sudo /app/auto-ansible/artifacts/auto-ansible.sh
```

A normal run applies the full host playbook from `main` and updates its monitoring
metrics. It waits for the interactive Ansible user to log out and checks for
another running playbook before proceeding. Local changes or divergent commits
in the runner's checkout prevent the update rather than being discarded.

## Test a branch or selected roles

Use debug mode for an interactive test:

```sh
sudo /app/auto-ansible/artifacts/auto-ansible.sh \
  --debug --tags media-server --branch my-test-branch
```

| Option | Behaviour |
| --- | --- |
| `--debug` | Enable test overrides, skip the login/logout check, and leave scheduled-run metrics unchanged |
| `--tags <tags>` | Run selected Ansible tags, separated by commas; requires `--debug` |
| `--branch <branch>` | Use the latest remote version of that branch; requires `--debug` |
| `--skip-user-logout-check` | Skip the login/logout check without enabling debug mode |

Debug mode uses a temporary checkout, preserving the scheduled checkout. It
reuses the installed dependencies and credentials. Without overrides it tests
`main` and the full playbook. Ansible's `always` tasks still run when tags are
selected.

Debug mode does not increase Ansible verbosity or reveal protected log output.
The check for another running playbook still applies.
