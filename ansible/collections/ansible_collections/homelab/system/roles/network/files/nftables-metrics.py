#!/usr/bin/python3
"""Export managed nftables counters through node exporter's textfile collector.

Installed on router nodes as homelab-firewall-metrics and run every 30 seconds
by a systemd timer. Requires Python's standard library, nft and CAP_NET_ADMIN.
Reads named counters from the ip firewall table using nft JSON.
Exports a fixed set of packet, byte and new-attempt metrics;
WAN interface totals are supplied separately by node exporter's network collector.

Atomically replaces /var/lib/node_exporter/textfile_collector/firewall.prom.
Collection failures publish health=0 without stale traffic metrics and return a
nonzero exit status. Collection timestamps allow detection of a stopped timer.
No firewall rules or counters are changed, and no network service is started.

Counters reset on table recreation; attempt packets are not unique sessions.
Forwarded packets are observations before later verdicts. Labels contain only
fixed categories, never client IP addresses, arbitrary ports or request paths.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

OUTPUT = Path('/var/lib/node_exporter/textfile_collector/firewall.prom')
CATEGORIES = ('web_allowed', 'turn_allowed', 'geoip_dropped', 'unknown_dropped',
              'invalid_dropped', 'ipv4_options_dropped', 'forward_observed')


@dataclass(frozen=True)
class Counter:
    packets: int
    bytes: int


def parse_counters(payload: object) -> dict[str, Counter]:
    """Validate nft JSON and convert managed counter values into typed objects."""
    if not isinstance(payload, dict) or not isinstance(payload.get('nftables'), list):
        raise ValueError('Expected an nftables JSON object containing a list')

    counters: dict[str, Counter] = {}

    for entry in payload['nftables']:
        if not isinstance(entry, dict):
            raise ValueError('Expected an nftables entry object')

        if 'counter' not in entry:
            continue  # nft also returns metadata entries.

        raw = entry['counter']
        if not isinstance(raw, dict):
            raise ValueError('Expected a counter object')

        if raw.get('family') != 'ip' or raw.get('table') != 'firewall':
            continue

        name = raw.get('name')

        if not isinstance(name, str):
            raise ValueError('Expected a counter name')

        packets, byte_count = raw.get('packets'), raw.get('bytes')
        # Reject booleans, strings and floats rather than silently coercing them.

        if type(packets) is not int or type(byte_count) is not int:
            raise ValueError(f'Expected integer values for counter {name}')

        if packets < 0 or byte_count < 0 or name in counters:
            raise ValueError(f'Negative values or duplicate counter {name}')

        counters[name] = Counter(packets=packets, bytes=byte_count)
    return counters


def render(counters: Mapping[str, Counter]) -> str:
    """Render validated counters; fail if an expected managed counter is absent."""
    lines = [
        '# HELP homelab_firewall_packets_total Packets at each decision or observation point.',
        '# TYPE homelab_firewall_packets_total counter',
        '# HELP homelab_firewall_bytes_total IPv4 bytes at each decision or observation point.',
        '# TYPE homelab_firewall_bytes_total counter',
        '# HELP homelab_firewall_new_packets_total New connection attempt packets; retransmissions may repeat.',
        '# TYPE homelab_firewall_new_packets_total counter',
    ]
    for category in CATEGORIES:
        counter = counters['wan_' + category]
        lines.append(f'homelab_firewall_packets_total{{category="{category}"}} {counter.packets}')
        lines.append(f'homelab_firewall_bytes_total{{category="{category}"}} {counter.bytes}')
        if category not in ('ipv4_options_dropped', 'invalid_dropped'):
            counter = counters['wan_' + category + '_new']
            lines.append(f'homelab_firewall_new_packets_total{{category="{category}"}} {counter.packets}')
    return '\n'.join(lines) + '\n'


def collect() -> int:
    try:
        result = subprocess.run(['/usr/sbin/nft', '-j', 'list', 'counters', 'ip'],
                                check=True, capture_output=True, text=True, timeout=10)
        metrics = render(parse_counters(json.loads(result.stdout)))
        status = 1
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        # Replace stale data on failure, never publish invented zero counters.
        metrics = ''
        status = 0
    metrics += '# HELP homelab_firewall_collection_success Whether the last collection succeeded.\n'
    metrics += '# TYPE homelab_firewall_collection_success gauge\n'
    metrics += f'homelab_firewall_collection_success {status}\n'
    metrics += '# HELP homelab_firewall_collection_timestamp_seconds Last collection attempt time.\n'
    metrics += '# TYPE homelab_firewall_collection_timestamp_seconds gauge\n'
    metrics += f'homelab_firewall_collection_timestamp_seconds {time.time():.3f}\n'

    with tempfile.NamedTemporaryFile(mode='w', dir=OUTPUT.parent, prefix='.firewall-', delete=False) as f:
        temporary = Path(f.name)
        try:
            f.write(metrics)
            f.flush()
            os.fchmod(f.fileno(), 0o644)
            os.replace(temporary, OUTPUT)
        finally:
            temporary.unlink(missing_ok=True)
    return 0 if status else 1


if __name__ == '__main__':
    raise SystemExit(collect())
