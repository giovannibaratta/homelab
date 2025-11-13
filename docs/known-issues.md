# Known Issues

## Podman Quadlet DNS updates

Podman Quadlet does not handle DNS update. If the list of the DNS servers changes, the network must be manually updated.

e.g.
```bash
podman network update netbird --dns-drop 172.16.255.254 --dns-add 172.16.255.252 --dns-add 172.16.255.253
```

## Error: mounting storage for container 

Try to delete the container, the image, the volume (if not persistent) and restart the service.