#!/usr/bin/env bash
# Open firewall for Recruiting Agent (run with sudo)
set -euo pipefail

PORT="${APP_PORT:-8510}"
PORT_END="${PORT_RANGE_END:-8520}"

echo "Opening TCP ports ${PORT}-${PORT_END}..."

if command -v ufw >/dev/null 2>&1; then
  ufw allow "${PORT}:${PORT_END}/tcp" comment "Recruiting Agent"
  ufw status | grep -E "${PORT}|Status"
elif command -v firewall-cmd >/dev/null 2>&1; then
  firewall-cmd --permanent --add-port="${PORT}-${PORT_END}/tcp"
  firewall-cmd --reload
  firewall-cmd --list-ports
else
  iptables -I INPUT -p tcp --dport "${PORT}" -j ACCEPT 2>/dev/null || true
  iptables -I INPUT -p tcp --dport "${PORT_END}" -j ACCEPT 2>/dev/null || true
  echo "Added iptables rules for port ${PORT}"
fi

echo "Done. Access: http://$(hostname -I | awk '{print $1}'):${PORT}"
