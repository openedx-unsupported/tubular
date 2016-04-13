#!/bin/bash
source go-agent-venv/bin/activate
export IN_VENV=1
if [ -n "$1" ]; then
    # The first argument is set, call back into specified program.
    $1 $2
fi
