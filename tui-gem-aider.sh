#!/bin/bash

set -ex

MODEL=gemini/gemini-2.5-pro



. ~/virtualenvs/aider_dev/bin/activate

#direnv reload

#  --restore-chat-history \
#  --llm-command "gemini_mod"
aider \
  --tui \
  --model $MODEL \
  --model-settings-file ~/model.settings.yml
