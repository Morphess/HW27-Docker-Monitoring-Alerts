#!/usr/bin/env python3
"""Run real production rules against isolated synthetic CPU/disk metrics, never host load."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
NAME = 'hw27-monitoring-safe-demo'
URL = 'http://127.0.0.1:9091'


def get(path):
    with urllib.request.urlopen(URL + path, timeout=5) as response:
        return json.load(response)


def wait_for(predicate, description, timeout=420):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                print(description, flush=True)
                return
        except (OSError, ValueError):
            pass
        time.sleep(5)
    raise RuntimeError('Timeout: ' + description)


class Metrics(BaseHTTPRequestHandler):
    healthy = False
    counter = 0.0
    previous = time.monotonic()

    def do_GET(self):
        now = time.monotonic()
        Metrics.counter += (now - Metrics.previous) * (1.0 if Metrics.healthy else 0.1)
        Metrics.previous = now
        available = 50 if Metrics.healthy else 10
        body = '\n'.join([
            '# HELP node_cpu_seconds_total Synthetic idle counter; NOT HOST DATA.',
            '# TYPE node_cpu_seconds_total counter',
            f'node_cpu_seconds_total{{cpu="0",mode="idle"}} {Metrics.counter}',
            f'node_cpu_seconds_total{{cpu="1",mode="idle"}} {Metrics.counter}',
            f'node_filesystem_avail_bytes{{device="DEMO",mountpoint="/",fstype="btrfs"}} {available}',
            'node_filesystem_size_bytes{device="DEMO",mountpoint="/",fstype="btrfs"} 100',
            'node_filesystem_readonly{device="DEMO",mountpoint="/",fstype="btrfs"} 0',
            '',
        ]).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; version=0.0.4')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def alerts():
    return get('/api/v1/alerts')['data']['alerts']


def main():
    # Bind before starting Docker. A port conflict cannot alter an existing service.
    server = ThreadingHTTPServer(('127.0.0.1', 9410), Metrics)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    started = False
    try:
        with tempfile.TemporaryDirectory(prefix='hw27-demo-') as directory:
            config = Path(directory) / 'prometheus.yml'
            config.write_text('''global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    project: hw27-monitoring
    demonstration: SAFE-SYNTHETIC-NOT-HOST
rule_files: [/rules/host-alerts.yml]
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['127.0.0.1:9093']
scrape_configs:
  - job_name: node-exporter
    static_configs:
      - targets: ['127.0.0.1:9410']
        labels:
          instance: DEMO-NOT-HOST:9100
          demonstration: SAFE-SYNTHETIC-NOT-HOST
''')
            subprocess.run(['docker', 'run', '-d', '--name', NAME,
                            '--label', 'com.docker.compose.project=hw27-monitoring-demo',
                            '--network', 'host', '--memory', '384m',
                            '--tmpfs', '/prometheus:rw,uid=65534,gid=65534,size=256m',
                            '-v', f'{config}:/etc/prometheus/prometheus.yml:ro,z',
                            '-v', f'{ROOT / "prometheus/rules"}:/rules:ro,z',
                            'prom/prometheus:v3.15.0',
                            '--config.file=/etc/prometheus/prometheus.yml',
                            '--storage.tsdb.path=/prometheus',
                            '--storage.tsdb.retention.time=1h',
                            '--web.listen-address=127.0.0.1:9091',
                            '--web.external-url=' + URL], check=True)
            started = True
            print('SAFE SYNTHETIC DEMO: http://127.0.0.1:9091/alerts ; host CPU/disk are untouched.', flush=True)
            wanted = {'HostDiskSpaceLow', 'HostHighCpuUsage'}
            wait_for(lambda: wanted <= {a['labels']['alertname'] for a in alerts() if a['state'] == 'firing'},
                     'Both production rules are FIRING on synthetic metrics.')
            input('Capture demo Prometheus and Alertmanager screenshots / Telegram FIRING, then press Enter to recover: ')
            Metrics.healthy = True
            print('Healthy synthetic metrics enabled; the unchanged 5m CPU window must recover.', flush=True)
            wait_for(lambda: not alerts(), 'Both production rules recovered (no active alerts).')
            # Allow AM group_interval to send RESOLVED before deleting the source.
            print('Waiting 45s for Alertmanager resolution delivery.', flush=True)
            time.sleep(45)
            input('Capture Telegram RESOLVED if enabled, then press Enter to remove the demo: ')
    finally:
        if started:
            subprocess.run(['docker', 'rm', '-f', NAME], check=True)
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nDemo stopped; its container and temporary configuration were removed.')
