#!/bin/sh
set -eu
# Database, session and upload files are private even inside the data volume.
umask 077
exec "$@"
