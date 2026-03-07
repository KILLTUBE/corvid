#!/bin/bash
echo "Activating virtual environment"
source ./corvid_venv_linux/bin/activate
exec "$SHELL"
