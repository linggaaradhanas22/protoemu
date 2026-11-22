#!/bin/bash
# Rebuild and run the EVAL-025 placement, replay and CTS checks.
set -e
pdk="${PDK_ROOT:?source scripts/env.sh first}/ciel/ihp-sg13/versions/89d42ee6d2fd9b50b86a1aada6fee6673c3e6008/ihp-sg13cmos5l"
tiles="$BUILD_DIR/tt/tech/ihp-sg13cmos5l/def/tt_block_8x4_pgvdd.def"
for v in v10 v10h; do
  extra=""
  top=full_core_probe
  if [ "$v" = v10h ]; then extra="--host-reg"; top=full_core_host; fi
  python3 -B -m models.physical.run_full_core_probe --opt 10 $extra \
    --work "test/sim_build/EVAL-025/$v" --out "design/evals/EVAL-025/$v" \
    --pdk "$pdk" --def "$tiles"
  python3 -B -m models.physical.run_full_core_cts --work "test/sim_build/EVAL-025/$v" \
    --out "design/evals/EVAL-025/$v" --top "$top" --pdk "$pdk" --def "$tiles"
done
python3 -B -m models.physical.run_full_core_replay --opt 10 --out design/evals/EVAL-025/v10/replay.json
