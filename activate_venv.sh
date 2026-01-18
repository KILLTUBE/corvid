#!/bin/bash
echo "Activating virtual environment"
source ./corvid_venv/bin/activate
exec "$SHELL"
