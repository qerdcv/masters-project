#!/usr/bin/env bash

set -eux

pip3 uninstall -y ansible

apt -y autoremove --purge
apt-get clean

sync
