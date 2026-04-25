#!/bin/bash
#
# Initialize compile-time deps (graphviz). Soft-fails with a warning so it
# is safe to use as a pixi activation hook.

echo "Registering graphviz plugins..."
if dot -c 2>&1; then
    echo "✓ Graphviz plugins registered successfully"
else
    echo "⚠ Warning: Failed to register graphviz plugins"
fi
