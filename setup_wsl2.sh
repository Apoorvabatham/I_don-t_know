#!/usr/bin/env bash
# One-time setup: run this yourself inside the WSL2 (Ubuntu) terminal.
# Requires sudo — you'll be prompted for your WSL2 password.
set -euo pipefail

echo "== Installing sandbox dependencies (bubblewrap, socat) =="
sudo apt-get update
sudo apt-get install -y bubblewrap socat

echo "== Installing Node.js LTS (needed for the Claude Code CLI) =="
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs

echo "== Installing Claude Code CLI =="
sudo npm install -g @anthropic-ai/claude-code

echo "== Installing the sandbox seccomp filter =="
echo "   (this is what actually blocks a sandboxed command from launching a Windows"
echo "   binary under /mnt/c — without it, that path is an open escape hatch)"
sudo npm install -g @anthropic-ai/sandbox-runtime

echo
echo "== Verifying =="
bwrap --version
socat -V 2>&1 | head -1
claude --version

echo
echo "Setup complete. Launch the build with:"
echo "  cd \"/mnt/c/Users/batha/I_don't_know\" && claude"
echo
echo "Then run /sandbox once inside Claude Code and confirm the Dependencies tab"
echo "is empty (all dependencies present) before letting it run unattended."
