# Backup

## ZITADEL Database Backup

```bash
systemctl stop zitadel
docker exec zitadel-db sh -c "pg_dump -U zitadeladmin zitadeldata > zitadeldata.bak"
docker cp zitadel-db:zitadeldata.bak zitadeldata.bak
```