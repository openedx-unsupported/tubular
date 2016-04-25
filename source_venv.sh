#!/bin/bash
source go-agent-venv/bin/activate
export IN_VENV=1
if [ -n "$1" ]; then
    # The first argument is set, which is assumed to be an executable.
    # Call the executable using all arguments.
    $@
fi
