# Known Issues

## Podman Quadlet DNS updates

Podman Quadlet does not handle DNS update. If the list of the DNS servers changes, the network must be manually updated.

e.g.
```bash
podman network update netbird --dns-drop 172.16.255.254 --dns-add 172.16.255.252 --dns-add 172.16.255.253
```

## Error: mounting storage for container 

```bash
podman system reset
```

This will delete all containers, images, volumes, and networks. Use with caution.

## Error: Porkbun DNS record creation fail

```bash
{"status":"ERROR","message":"Create error: We were unable to create the DNS record."}
Status Code: 400
```

Try to cleanup unnecessary TXT records if present.

### Script for cleaning up TXT challenges

1. Open the Porkbun UI
1. Open the manage DNS records
1. Sniff the API response from the developer tools of the `getDomainDNS` request
1. Save the JSON in `/tmp/records.json`
1. Run the script

   ```bash
   # 1. Get the IDs
   DOMAIN=""
   SECRET_API_KEY=""
   API_KEY=""
   RECORDS=$(jq -r '.dnsRecords[] | select(.type == "TXT" and (.name | startswith("_acme-challenge"))) | .id' /tmp/records.json)

   # 2. Delete the records
   echo "$RECORDS" | while read -r ID; do
       # Skip empty lines if any
       [ -z "$ID" ] && continue

       echo "Deleting record: $ID"

       curl -s -X POST "https://api.porkbun.com/api/json/v3/dns/delete/$DOMAIN/$ID" \
            -H "Content-Type: application/json" \
            -d "{
                  \"secretapikey\": \"$SECRET_API_KEY\",
                  \"apikey\": \"$API_KEY\"
                }"

       # Add a tiny sleep to be nice to the API
       sleep 0.5
   done
   ```