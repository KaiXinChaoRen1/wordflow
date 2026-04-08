#!/bin/sh

set -eu

cd "$(dirname "$0")"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src exec python3 -m wordflow
