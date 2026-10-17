# Docker monitoring and alerts

Prometheus, Grafana, Alertmanager, Node Exporter and cAdvisor run in Docker. Telegram is **disabled by default**, so the stack works without a bot. Its delivery is **not verified yet**.

```sh
# Optional, before the first Grafana start:
cp .env.example .env
# Edit .env to choose your own Grafana password.
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
```

| Interface | Local address |
| --- | --- |
| Grafana | http://127.0.0.1:3000 |
| Prometheus / targets | http://127.0.0.1:9090/targets |
| Alertmanager | http://127.0.0.1:9093 |
| cAdvisor | http://127.0.0.1:8080 |
| Node Exporter | http://127.0.0.1:9100/metrics |

Grafana login: `admin`; default local-only password: `hw27-local-admin-change-me`, unless changed through `.env` before initialization. An existing Grafana volume keeps its password. Dashboards are in **Docker Monitoring**. Wait at least two scrapes for rates; CPU alerts use a 5-minute window.

Pinned developer images: Prometheus **3.15.0**, Grafana **13.2.4**, Alertmanager **0.34.1**, Node Exporter **1.12.1**, cAdvisor **0.60.6**. Prometheus (7 days / 2 GB), Grafana and Alertmanager use named volumes. No custom Dockerfiles.

## Host access and security

This setup targets native Linux, not Docker Desktop. Verified environment: Fedora 44, Docker Engine 29.7.2, Compose 5.5.1, systemd cgroups v2, SELinux **Enforcing**, 12 logical CPUs. Existing homework services are not modified.

All services intentionally use host networking and explicitly bind their HTTP listener to **127.0.0.1**. Node Exporter also uses the host PID namespace and `/:/host:ro,rslave`, with matching root/proc/sys paths: CPU, RAM, mounted disks and network interfaces describe the host, not the exporter container. On Docker Desktop these namespaces and mounts describe the Linux VM, **not the desktop OS**; this stack is not claimed portable to Desktop. The friendly `fedora:9100` instance label is configured in `prometheus/prometheus.yml`.

Exporters alone use `label=disable` for access to host-labelled files; SELinux remains globally enforcing. Host mounts are not relabelled. Project configuration mounts use shared `:z` labels. Neither exporter is privileged. cAdvisor uses the host cgroup namespace and read-only root/sys/Docker-state mounts. Its Docker socket supplies metadata and useful container names. Docker 29's `overlayfs` containerd snapshotter also requires `/run/containerd/containerd.sock`: without it, cAdvisor's Docker factory failed to register on this host. **Read-only socket mounts do not make either API read-only**; both powerful sockets are given only to cAdvisor. Do not expose this monitoring stack remotely.

## Community dashboards

Complete JSON files are saved under `grafana/dashboards/`; no online import is needed on restart. Datasource **Prometheus**, UID `prometheus`, is provisioned automatically.

| Dashboard | Community ID / revision | Local JSON |
| --- | --- | --- |
| [Node Exporter Full](https://grafana.com/grafana/dashboards/1860-node-exporter-full/) | 1860 / 45 | [host JSON](grafana/dashboards/node-exporter-full.json) |
| [cAdvisor exporter — Docker containers Overview](https://grafana.com/grafana/dashboards/21743-cadvisor-exporter-docker-containers-overview/) | 21743 / 3 | [container JSON](grafana/dashboards/cadvisor-containers.json) |

Sources: [1860 revision 45 download](https://grafana.com/api/dashboards/1860/revisions/45/download), [21743 revision 3 download](https://grafana.com/api/dashboards/21743/revisions/3/download). Local adaptations fix datasource UID, job filters, initial variables and 15s refresh. Community layouts are retained. Container CPU uses **100% = one CPU core**, not 100% of the entire host. The upstream count panel is correctly named “Container instances observed”, not “restarts”.

## Alerts and checks

| Rule | Condition | Hold |
| --- | --- | --- |
| HostDiskSpaceLow | `100 * available bytes / size bytes < 15` on writable real host filesystems | 2m |
| HostHighCpuUsage | `100 * (1 - avg by(instance, job)(rate(idle[5m]))) > 80` | 2m |
| PrometheusTargetDown | `up == 0` for any configured target | 1m |

Disk rules exclude pseudo filesystems and container service mounts, plus read-only filesystems. The real btrfs `/` is retained. CPU is averaged across cores independently per instance/job. Alert annotations contain instance, job, current value and threshold. Prometheus sends alerts to Alertmanager. Group wait is 10s, group interval 30s, repeats every 4h; Telegram sends FIRING and RESOLVED when enabled.

```sh
docker compose run --rm --no-deps --entrypoint promtool prometheus check config /etc/prometheus/prometheus.yml
docker compose run --rm --no-deps --entrypoint promtool prometheus test rules /tests/alerts.test.yml
docker compose run --rm --no-deps --entrypoint amtool alertmanager check-config /etc/alertmanager/alertmanager.yml
```

Tests use the actual production rules: disk 14/15/16%, CPU 79/80/81%, per-core/per-instance aggregation, filesystem exclusions, hold times and target recovery. Exactly 15% free and exactly 80% busy do **not** fire.

Safe live demonstrations (interactive; press Enter only after capturing screenshots):

```sh
python3 scripts/demo.py
python3 scripts/target-down.py
```

`demo.py` runs a separate temporary Prometheus at http://127.0.0.1:9091/alerts using the **unchanged production rules** and isolated synthetic metrics at port 9410. Instance `DEMO-NOT-HOST:9100` and label `SAFE-SYNTHETIC-NOT-HOST` clearly mark the demonstration. It simulates 10% disk availability and 90% CPU busy; then 50% available and idle CPU for recovery. It does not fill a disk or generate CPU load. Expect several minutes for `for` timers and recovery of the 5m rate window. Demo storage is a bounded in-memory tmpfs: no Docker data volume is created or deleted. Its container and temporary configuration are removed on exit. This proves rule evaluation and forwarding, **not a real host threshold breach**.

`target-down.py` stops only this project's Node Exporter, waits for real PrometheusTargetDown FIRING, then restarts it and checks recovery. The exporter is also restored on Ctrl+C/errors. After either demonstration, check all four production targets are UP. No alerts are injected directly into the Alertmanager API.

Verified locally: Compose config, promtool config/rules and all four test groups passed; both community dashboards displayed live data. All three alerts reached Alertmanager and recovered. The normal thresholds were never changed. The root btrfs filesystem had about **16.9% available**, so no real disk threshold breach is claimed. The isolated demo was removed. The optional Telegram override and `bot_token_file` configuration passed amtool with dummy data only; no Telegram delivery was attempted.

## Enable Telegram later

1. In Telegram open the official **@BotFather**, send `/newbot`, choose a name and username, and save its token locally.
2. Open your new bot and send `/start` from the private chat intended for this homework.
3. Copy the examples below. Put only the real `123456789:ABC...` token on one line in `local/telegram_bot_token`. Run `python3 scripts/telegram.py chat-id`: it calls **api.telegram.org directly**, prints chat IDs, and never prints the token. No third-party token service is used.
4. Put the intended private chat's numeric ID on one line in `local/telegram_chat_id` (no quotes or `chat_id=` prefix). Do not select somebody else's chat.
5. Run `python3 scripts/telegram.py enable`. It validates the generated configuration and recreates **only Alertmanager** with its Telegram override and mounted token secret. The token is read with supported `bot_token_file`, not `.env` expansion.
6. Run `python3 scripts/target-down.py`; wait for Telegram **FIRING**, press Enter to restart the exporter, then confirm **RESOLVED**. Add genuine screenshots as `screenshots/telegram-firing.png` and `screenshots/telegram-resolved.png`. Optionally repeat `scripts/demo.py` for synthetic CPU/disk messages.

```sh
cp local/telegram_bot_token.example local/telegram_bot_token
cp local/telegram_chat_id.example local/telegram_chat_id
chmod 700 local
chmod 600 local/telegram_bot_token
# Edit these two local files, then:
python3 scripts/telegram.py chat-id
python3 scripts/telegram.py enable
```

## Screenshots

Only genuine browser captures are included. CPU/disk alert captures show synthetic data, not host stress. Telegram captures must be added after real delivery.

- [Running containers: actual cAdvisor Docker inventory](screenshots/running-containers.png)
- [All four Prometheus targets UP](screenshots/prometheus-targets.png)
- [Real host root filesystem availability query](screenshots/host-metrics.png)
- [Named container CPU query](screenshots/container-metrics.png)
- [Host community dashboard](screenshots/grafana-host.png)
- [Container community dashboard](screenshots/grafana-containers.png)
- [HostDiskSpaceLow — synthetic demo](screenshots/alert-disk-demo.png)
- [HostHighCpuUsage — synthetic demo](screenshots/alert-cpu-demo.png)
- [PrometheusTargetDown — real exporter outage](screenshots/alert-target-down.png)
- [All three alerts received by Alertmanager](screenshots/alertmanager-alerts.png)
- [Synthetic demonstration rules recovered](screenshots/demo-alerts-recovered.png)
- [Alertmanager after all alerts recovered](screenshots/alertmanager-recovered.png)

## Stop

```sh
docker compose stop       # keep containers and all data
# Or remove only this project's containers; named data volumes remain:
docker compose down
```
## Author 
Morphes

