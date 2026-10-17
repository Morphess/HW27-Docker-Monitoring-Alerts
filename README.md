# Docker Monitoring & Alerts

This project monitors the host system and Docker containers with Prometheus, Grafana, Node Exporter and cAdvisor. Alertmanager sends alerts to Telegram when it is configured.

## Start

For the first run, copy the example settings and set your Grafana password in `.env`:

```bash
cp .env.example .env
```

Start the stack:

```bash
docker compose pull
docker compose up -d
docker compose ps
```

| Service | Address |
| --- | --- |
| Grafana | http://127.0.0.1:3000 |
| Prometheus targets | http://127.0.0.1:9090/targets |
| Alertmanager | http://127.0.0.1:9093 |
| cAdvisor | http://127.0.0.1:8080 |
| Node Exporter | http://127.0.0.1:9100/metrics |

Grafana username: `admin`. If no password was set, the default is `hw27-local-admin-change-me`. Changing `.env` does not reset the password in an existing Grafana volume.

## Dashboards

Open the **Docker Monitoring** folder in Grafana. The datasource and dashboards are loaded automatically.

- [Node Exporter Full — ID 1860, revision 45](https://grafana.com/grafana/dashboards/1860-node-exporter-full/): CPU, RAM, disk and network.
- [cAdvisor — ID 21743, revision 3](https://grafana.com/grafana/dashboards/21743-cadvisor-exporter-docker-containers-overview/): Docker container metrics.

Dashboard JSON files are stored in `grafana/dashboards/`. Allow a little time after startup for graphs to show data.

## Alerts

| Alert | Condition | Duration |
| --- | --- | --- |
| HostDiskSpaceLow | Available disk space below 15% | 2 minutes |
| HostHighCpuUsage | Average CPU usage above 80%, measured over 5 minutes | 2 minutes |
| PrometheusTargetDown | A monitored target is unavailable | 1 minute |

## Telegram

Telegram is disabled by default. To enable it:

1. Create a bot through **@BotFather** using `/newbot`.
2. Open your bot and send `/start`.
3. Prepare the local files:

```bash
cp local/telegram_bot_token.example local/telegram_bot_token
cp local/telegram_chat_id.example local/telegram_chat_id
chmod 700 local
chmod 600 local/telegram_bot_token
```

4. Put the bot token in `local/telegram_bot_token`, then run:

```bash
python3 scripts/telegram.py chat-id
```

5. Put your private chat's numeric ID in `local/telegram_chat_id`. Use the chat ID returned for your message, not the bot's ID. Each file should contain only its value on one line.
6. Apply the settings:

```bash
python3 scripts/telegram.py enable
```

Keep the token private and do not commit the local credential files.

## Check the alerts

To test an unavailable target:

```bash
python3 scripts/target-down.py
```

The script stops this project's Node Exporter. Wait for the Telegram **FIRING** message, then press Enter to restore it. Check that **RESOLVED** arrives too.

To demonstrate the CPU and disk alerts:

```bash
python3 scripts/demo.py
```

This uses a separate test instance with synthetic metrics. It does not fill the host disk or create CPU load. Wait for the alerts, then follow the script's instructions to check recovery.

To run the alert rule tests:

```bash
docker compose run --rm --no-deps --entrypoint promtool prometheus test rules /tests/alerts.test.yml
```

## Screenshots

- [Running containers](screenshots/running-containers.png)
- [Prometheus targets](screenshots/prometheus-targets.png)
- [Host metrics](screenshots/host-metrics.png)
- [Container metrics](screenshots/container-metrics.png)
- [Host dashboard](screenshots/grafana-host.png)
- [Container dashboard](screenshots/grafana-containers.png)
- [Disk alert — synthetic demo](screenshots/alert-disk-demo.png)
- [CPU alert — synthetic demo](screenshots/alert-cpu-demo.png)
- [Unavailable target alert](screenshots/alert-target-down.png)
- [Alerts in Alertmanager](screenshots/alertmanager-alerts.png)
- [Demo recovery](screenshots/demo-alerts-recovered.png)
- [Alertmanager after recovery](screenshots/alertmanager-recovered.png)

After checking Telegram delivery, save its screenshots as `screenshots/telegram-firing.png` and `screenshots/telegram-resolved.png`.

## Stop

```bash
docker compose stop
```

Use `docker compose up -d` to start again. Data is kept in named volumes.

## Author

Morphes

