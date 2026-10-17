#!/usr/bin/env python3
"""Explicit local Telegram setup; never prints the token or API URL."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'local'
BASE = ['docker', 'compose', '-f', 'docker-compose.yaml']
TELEGRAM = BASE + ['-f', 'docker-compose.telegram.yaml']


def token():
    value = (LOCAL / 'telegram_bot_token').read_text().strip()
    if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+', value):
        raise ValueError('Invalid bot token format in local/telegram_bot_token')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['chat-id', 'enable', 'disable'])
    action = parser.parse_args().action
    os.chdir(ROOT)
    if action == 'disable':
        subprocess.run(BASE + ['up', '-d', '--no-deps', '--force-recreate', 'alertmanager'], check=True)
        return
    value = token()
    if action == 'chat-id':
        try:
            with urllib.request.urlopen('https://api.telegram.org/bot' + value + '/getUpdates', timeout=20) as response:
                data = json.load(response)
        except urllib.error.HTTPError as error:
            raise ValueError(f'Telegram API returned HTTP {error.code}; check the local token') from None
        except urllib.error.URLError:
            raise ValueError('Cannot reach api.telegram.org; check network access') from None
        chats = {(item['message']['chat']['id'], item['message']['chat']['type'])
                 for item in data.get('result', []) if 'message' in item}
        if not chats:
            print('No messages found. Send /start to your bot, then run this command again.')
        for chat_id, kind in sorted(chats):
            print(f'chat_id={chat_id} type={kind}')
        return
    chat_id = (LOCAL / 'telegram_chat_id').read_text().strip()
    if not re.fullmatch(r'-?[1-9][0-9]*', chat_id):
        raise ValueError('local/telegram_chat_id must contain one nonzero signed integer')
    # Protect traversal on the host; Alertmanager UID 65534 must read the mounted secret.
    LOCAL.chmod(0o700)
    (LOCAL / 'telegram_bot_token').chmod(0o644)
    rendered = (ROOT / 'alertmanager/telegram.yml.example').read_text().replace('CHAT_ID_PLACEHOLDER', chat_id)
    (LOCAL / 'alertmanager.telegram.yml').write_text(rendered)
    subprocess.run(TELEGRAM + ['config', '--quiet'], check=True)
    subprocess.run(TELEGRAM + ['run', '--rm', '--no-deps', '--entrypoint', 'amtool',
                              'alertmanager', 'check-config', '/etc/alertmanager/alertmanager.yml'], check=True)
    subprocess.run(TELEGRAM + ['up', '-d', '--no-deps', '--force-recreate', 'alertmanager'], check=True)
    print('Telegram receiver enabled. Verify real FIRING and RESOLVED delivery before claiming success.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
