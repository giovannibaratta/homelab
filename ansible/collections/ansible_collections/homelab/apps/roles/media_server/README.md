# Media servers

This role deploys Plex, Jellyfin, or both as Podman services. It manages their
container configuration, persistent storage locations, and service lifecycle.
Jellyfin also supports hardware acceleration and configuration through inventory.

Users, libraries, passwords, plugins, and watch history are managed in the
applications. Complete their initial setup after deployment.

## Choose which servers to run

Enable the role on a host with `deploy_mediastack: true`, then select a deployment
type:

| `media_server_deployment_type` | Services enabled |
| --- | --- |
| `plex` (default) | Plex |
| `jellyfin` | Jellyfin |
| `multi` | Services explicitly enabled by the two options below |

For example, to run both:

```yaml
deploy_mediastack: true
media_server_deployment_type: multi
media_server_multi_deploy_plex: true
media_server_multi_deploy_jellyfin: true
```

Setting `deploy_mediastack: false` disables both services. Changing the selection
also stops and removes the service definitions for components no longer enabled;
application data and media are retained.

## Jellyfin hardware acceleration

Hardware acceleration defaults to `none` (CPU processing). To detect a supported
AMD or Intel GPU automatically:

```yaml
media_server_jellyfin_hardware_acceleration: auto
```

| Value | Behaviour |
| --- | --- |
| `none` | Use the CPU |
| `auto` | Select VA-API for a supported AMD or Intel GPU; fall back to CPU if none is found |
| `vaapi` | Explicitly select VA-API |
| `qsv` | Explicitly select Intel Quick Sync |

When multiple supported GPUs are present, choose one with
`media_server_jellyfin_render_device` using its host render-device path. The host
must already have a working GPU driver. Available codecs depend on the hardware;
verify acceleration with a transcoded playback session. Direct Play does not
normally use the transcoding GPU.

## Jellyfin preferences and access

The role manages selected network, general, and encoding settings. Changes made
to those same settings in Jellyfin are restored from inventory on a subsequent
service start or deployment. Other application settings are preserved.

Common options include:

| Variable | Purpose |
| --- | --- |
| `media_server_jellyfin_domain` | Web address; defaults to `tv.{{ internal_domain }}` |
| `media_server_jellyfin_system_settings` | General preferences, such as the server name and Quick Connect |
| `media_server_jellyfin_local_networks` | Networks Jellyfin should treat as local; defaults to the configured internal network |
| `media_server_jellyfin_allow_remote_access` | Jellyfin's own remote-access setting; defaults to `false` and does not create a public route |
| `media_server_jellyfin_manage_network` | Whether the role manages Jellyfin network settings; defaults to `true` |
| `media_server_jellyfin_manage_encoding` | Whether the role manages Jellyfin encoding settings; defaults to `true` |

For example:

```yaml
media_server_jellyfin_system_settings:
  ServerName: Home TV
  QuickConnectAvailable: true
```

Use `media_server_jellyfin_system_settings: {}` to leave general preferences
application-managed. Advanced network and encoding overrides are available through
`media_server_jellyfin_network_settings` and
`media_server_jellyfin_encoding_settings`; these require settings supported by the
selected Jellyfin version.

## Versions and storage

`media_server_plex_version` and `media_server_jellyfin_version` select container
versions. Configuration and cache locations can also be overridden through the
role variables. See [defaults/main.yaml](defaults/main.yaml) for the full list
and current defaults.

Apply changes through the usual homelab deployment workflow using the
`media-server` tag and the desired host limit.
