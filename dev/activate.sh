#!/bin/bash

echo "Running activation scripts..."

# Register graphviz plugins
echo "Registering graphviz plugins..."
if dot -c 2>&1; then
    echo "✓ Graphviz plugins registered successfully"
else
    echo "⚠ Warning: Failed to register graphviz plugins"
fi

# Install playwright browsers
echo "Installing playwright chromium browser..."
if playwright install --with-deps chromium 2>&1 | grep -q "chromium"; then
    echo "✓ Playwright chromium installed successfully"
else
    echo "⚠ Warning: Failed to install playwright chromium"
fi

echo "Activation complete!"
