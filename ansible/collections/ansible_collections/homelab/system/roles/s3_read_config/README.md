# Read published configuration from S3

This role loads a JSON configuration file from an existing S3-compatible bucket
and makes its outputs available to subsequent Ansible tasks. It reads the object
without changing the bucket or saving a local copy of the configuration file.

Use it to share published application settings or credentials between deployments.
The role does not require access to Terraform or its working directory.

## Configuration

All connection settings must be supplied by the caller:

| Variable | Purpose |
| --- | --- |
| `s3_read_config_endpoint` | S3 endpoint URL; use HTTPS for sensitive configuration |
| `s3_read_config_bucket` | Existing bucket name |
| `s3_read_config_object_key` | Configuration object's exact key |
| `s3_read_config_region` | Request-signing region |
| `s3_read_config_access_key` | Access key ID |
| `s3_read_config_secret_key` | Secret access key |

Provide credentials through your secret-management configuration. They need
`ListBucket` permission for the object's key prefix and `GetObject` permission
for the object; write permissions are unnecessary.

The executing host must be able to reach the endpoint and have compatible
`boto3` and `botocore` Python packages installed. The controller requires the
`amazon.aws` collection (`>=9.2,<10`).

## Usage

```yaml
- name: Load published settings
  ansible.builtin.import_role:
    name: homelab.system.s3_read_config
  vars:
    s3_read_config_endpoint: https://s3.example.org
    s3_read_config_bucket: private-configuration
    s3_read_config_object_key: application/outputs.json
    s3_read_config_region: us-east-1
    s3_read_config_access_key: "{{ vault_s3_access_key }}"
    s3_read_config_secret_key: "{{ vault_s3_secret_key }}"
```

The object must contain a JSON envelope with schema version `1` and an `outputs`
object:

```json
{
  "schema_version": 1,
  "outputs": {
    "application_client_id": "example-client"
  }
}
```

Output names and values are application-defined. Consumers must check that the
fields they need are present. Empty outputs are valid.

## Results and failures

| Returned fact | Meaning |
| --- | --- |
| `s3_read_config_available` | Whether the object was found and successfully validated |
| `s3_read_config_outputs` | Published outputs, or an empty dictionary if the object is absent |

A missing object is allowed, so deployments can handle configuration that has
not yet been published. Missing buckets, permission or connection errors, and
invalid configuration fail the run instead of being treated as an absent object.

The read runs once per play batch. Use Ansible's linear strategy; serial batches
perform a separate read for each batch.

The role protects sensitive task output. Treat returned values as sensitive too,
and avoid printing them in subsequent tasks.
