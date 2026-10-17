#!/usr/bin/env python3
"""Stop ONLY this homework's Node Exporter; always restart it on exit."""
import json
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ['docker', 'compose', '-f', str(ROOT / 'docker-compose.yaml')]


def alerts():
    with urllib.request.urlopen('http://127.0.0.1:9090/api/v1/alerts', timeout=5) as response:
        return [a for a in json.load(response)['data']['alerts']
                if a['labels']['alertname'] == 'PrometheusTargetDown'
                and a['labels']['job'] == 'node-exporter']


def wait_for(predicate, message):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if predicate():
            print(message, flush=True)
            return
        time.sleep(5)
    raise RuntimeError('Timeout: ' + message)


def main():
    try:
        subprocess.run(COMPOSE + ['stop', 'node-exporter'], check=True, cwd=ROOT)
        wait_for(lambda: any(a['state'] == 'firing' for a in alerts()),
                 'PrometheusTargetDown FIRING for the real homework exporter.')
        input('Capture Prometheus / Alertmanager and Telegram FIRING if enabled; press Enter to restore: ')
    finally:
        subprocess.run(COMPOSE + ['start', 'node-exporter'], check=True, cwd=ROOT)
    wait_for(lambda: not alerts(), 'PrometheusTargetDown recovered.')
    print('Allowing 45s for Alertmanager RESOLVED delivery.', flush=True)
    time.sleep(45)
    print('Check Telegram RESOLVED if enabled. Node Exporter is running again.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nExporter restored by the finally handler.')
