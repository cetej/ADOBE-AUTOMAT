#!/bin/bash
# PostCompact hook — remind to checkpoint after context compaction
# Compaction means context is getting large, good time to save state

echo "Context was compacted. Consider running /checkpoint save to preserve session state."
