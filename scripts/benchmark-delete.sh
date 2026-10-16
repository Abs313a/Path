#!/usr/bin/env bash
set -euo pipefail

scale="${PATHFM_DELETE_BENCH_SCALE:-0}"
if [[ "$scale" == 1 ]]; then
  files="${PATHFM_DELETE_BENCH_FILES:-1000000}"
  test_name='adapters::local_operations::tests::benchmark_parallel_delete_scale'
else
  files="${PATHFM_DELETE_BENCH_FILES:-100000}"
  test_name='adapters::local_operations::tests::benchmark_delete_large_directory'
fi
benchmark_root="${PATHFM_DELETE_BENCH_ROOT:-$PWD/target/delete-benchmark}"
mkdir -p "$benchmark_root"

printf 'Deleting %s files (override with PATHFM_DELETE_BENCH_FILES)\n' "$files"
printf 'Filesystem: %s; CPUs: %s\n' "$(stat -f -c %T "$benchmark_root")" "$(nproc)"
PATHFM_DELETE_BENCH_FILES="$files" \
PATHFM_DELETE_BENCH_ROOT="$benchmark_root" \
  ./scripts/test-headless.py \
  "$test_name" \
  -- --ignored --exact --nocapture --test-threads=1
