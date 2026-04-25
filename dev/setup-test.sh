#!/bin/bash
#
# Initialize test-time deps (playwright chromium). Soft-fails with a warning
# so it is safe to use as a pixi activation hook.

echo "Installing playwright chromium browser..."
if playwright install --with-deps chromium > /dev/null 2>&1; then
    echo "✓ Playwright chromium installed successfully"
else
    echo "⚠ Warning: Failed to install playwright chromium"
fi
