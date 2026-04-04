#!/usr/bin/env bash
# ★ PoC 전용 — Check which CLI tools are available

echo "=== CLI Tool Availability Check ==="
echo

for tool in claude codex gemini; do
    if command -v "$tool" &>/dev/null; then
        version=$("$tool" --version 2>/dev/null || echo "unknown")
        echo "  [OK] $tool — $version"
    else
        echo "  [--] $tool — not installed"
    fi
done

echo
echo "=== API Key Check ==="
echo

for var in ANTHROPIC_API_KEY CODEX_API_KEY GEMINI_API_KEY; do
    if [ -n "${!var}" ]; then
        echo "  [OK] $var — set (${#!var} chars)"
    else
        echo "  [--] $var — not set"
    fi
done
