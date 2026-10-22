# s3_read_config

Reads a versioned JSON configuration artifact from an existing S3-compatible
bucket and exposes its output dictionary as Ansible facts. The role reads the
object into memory without saving an artifact file or modifying the bucket.

## Requirements

- Controller: the `amazon.aws` collection, version `>=9.2,<10`.
- Executing host: Python with boto3 and botocore compatible with that collection.
- Network access from the executing host to the S3 endpoint.
- Credentials permitting `ListBucket` for the object-key prefix and `GetObject`
  for the exact object. No write permissions are required.

The role does not install dependencies. Its tasks use `run_once`, executing on
one targeted host and sharing the resulting facts with the current play batch.
Use Ansible's linear strategy. With `serial`, the read repeats for each batch.

## Required inputs

All inputs must be provided explicitly; none have defaults.

| Variable | Value |
| --- | --- |
| `s3_read_config_endpoint` | S3-compatible endpoint URL. Use HTTPS for credentials and sensitive configuration. |
| `s3_read_config_bucket` | Existing bucket name. |
| `s3_read_config_object_key` | Exact object key within the bucket. |
| `s3_read_config_region` | S3 request-signing region. |
| `s3_read_config_access_key` | Access key ID. |
| `s3_read_config_secret_key` | Secret access key. |

## Usage

```yaml
- name: Read configuration
  hosts: application_hosts
  gather_facts: false
  tasks:
    - name: Load published configuration
      ansible.builtin.import_role:
        name: homelab.system.s3_read_config
      vars:
        s3_read_config_endpoint: "https://s3.example.org"
        s3_read_config_bucket: "private-configuration"
        s3_read_config_object_key: "identity/outputs.json"
        s3_read_config_region: "us-east-1"
        s3_read_config_access_key: "{{ vault_s3_access_key }}"
        s3_read_config_secret_key: "{{ vault_s3_secret_key }}"
```

Supply the credential variables using an appropriate secret source. No fixed
host, Terraform executable or Terraform working directory is required.

## Artifact format

The object must contain a JSON document with this envelope:

```json
{
  "schema_version": 1,
  "outputs": {
    "application_client_id": "example-client",
    "application_client_secret": "example-secret"
  }
}
```

Only schema version `1` is supported. `outputs` must be a JSON object; an empty
object is valid. Output names and values are application-defined. The role does
not require particular keys or validate individual values. Code using the
returned dictionary must validate the fields it needs.

## Returned facts

| Fact | Meaning |
| --- | --- |
| `s3_read_config_available` | `true` when an existing artifact was read and validated, including one with empty outputs; otherwise `false`. |
| `s3_read_config_outputs` | The artifact's `outputs` dictionary, or `{}` when the object is absent. |

Both facts are reset before each read. They are not marked cacheable. Sensitive
tasks use `no_log: true`, and intermediate artifact content is discarded after
the read/validation block. Treat returned values as sensitive and avoid printing
them in subsequent tasks.

## Missing objects and failures

The role lists the configured key prefix and checks for the exact object key.
If the bucket exists but that object is absent, it completes successfully with
`available: false` and an empty output dictionary. It does not create the object
or wait for it to appear.

Invalid inputs, missing buckets, denied access, network errors, malformed JSON,
unsupported schema versions and a non-object `outputs` value fail the run.
These failures are not treated as missing configuration. Read failures also
remain failures if an object disappears between listing and retrieval.
