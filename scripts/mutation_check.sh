#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Deliberately breaks the code/baselines/config each e2e suite is supposed to guard, and proves
# the listed pytest target goes red. A survivor means that suite is toothless for this mutation
# -- tighten the corresponding assertion, never weaken the mutation.
#
# | # | Mutation                                                    | Suite that must fail          |
# |---|--------------------------------------------------------------|--------------------------------|
# | 1 | features.py: lag 28 -> 29                                   | full suite (training+inference e2e) |
# | 2 | features.py: Is_Weekend [5, 6] -> [4, 6]                    | full suite (forecasting/features_test.py) |
# | 3 | training baseline csv: first prediction += 10               | src/training (PREDICTION_ATOL) |
# | 4 | inference baseline csv: first prediction += 10              | src/inference                 |
# | 5 | inference forecast_metadata.joblib renamed away             | src/inference (fail-fast)     |
# | 6 | inference config.toml: artifact_dir -> "nowhere"            | inference config_test.py      |
# | 7 | result_upload.py: predicted_quantity int(...) -> int(...)+1 | src/inference (upload payload) |

FEATURES="src/forecasting/forecasting/features.py"
TRAINING_BASELINE="src/training/tests/baseline/next_day_product_forecast.csv"
INFERENCE_BASELINE="src/inference/tests/baseline/inference_next_day_forecast.csv"
INFERENCE_METADATA="src/inference/tests/baseline/forecast_metadata.joblib"
INFERENCE_CONFIG="src/inference/inference/config.toml"
RESULT_UPLOAD="src/inference/inference/result_upload.py"

MUTATED_FILES=("$FEATURES" "$TRAINING_BASELINE" "$INFERENCE_BASELINE" "$INFERENCE_METADATA" "$INFERENCE_CONFIG" "$RESULT_UPLOAD")

if [[ -n "$(git status --porcelain -- "${MUTATED_FILES[@]}")" ]]; then
    echo "ABORT: uncommitted changes in files this script mutates -- commit or stash first." >&2
    git status --porcelain -- "${MUTATED_FILES[@]}" >&2
    exit 1
fi

SURVIVORS=0

bump_first_prediction() {
    python3 -c "
import csv, sys
path = sys.argv[1]
with open(path, newline='') as f:
    rows = list(csv.reader(f))
rows[1][-1] = str(int(rows[1][-1]) + 10)
with open(path, 'w', newline='') as f:
    csv.writer(f).writerows(rows)
" "$1"
}

mutate() {
    local n="$1" file="$2" apply_cmd="$3" pytest_target="$4"

    eval "$apply_cmd"

    if uv run pytest $pytest_target -q >/tmp/mutation_check_"$n".log 2>&1; then
        echo "FAIL mutation $n survived ($file, target: $pytest_target)"
        SURVIVORS=$((SURVIVORS + 1))
    else
        echo "PASS mutation $n caught"
    fi

    if [[ -e "$file.bak" ]]; then
        mv "$file.bak" "$file"
    else
        git checkout -- "$file"
    fi
}

mutate 1 "$FEATURES" \
    "sed -i 's/for lag in \[1, 7, 14, 28\]/for lag in [1, 7, 14, 29]/' $FEATURES" \
    ""

mutate 2 "$FEATURES" \
    "sed -i 's/\.isin(\[5, 6\])/.isin([4, 6])/' $FEATURES" \
    ""

mutate 3 "$TRAINING_BASELINE" \
    "bump_first_prediction $TRAINING_BASELINE" \
    "src/training -m e2e"

mutate 4 "$INFERENCE_BASELINE" \
    "bump_first_prediction $INFERENCE_BASELINE" \
    "src/inference -m e2e"

mutate 5 "$INFERENCE_METADATA" \
    "mv $INFERENCE_METADATA $INFERENCE_METADATA.bak" \
    "src/inference -m e2e"

mutate 6 "$INFERENCE_CONFIG" \
    "sed -i 's/artifact_dir = \"outputs\"/artifact_dir = \"nowhere\"/' $INFERENCE_CONFIG" \
    "src/inference/inference/config_test.py"

mutate 7 "$RESULT_UPLOAD" \
    "sed -i 's/predicted_quantity=int(cast(\"int\", row\[\"Predicted_Qty\"\]))/predicted_quantity=int(cast(\"int\", row[\"Predicted_Qty\"])) + 1/' $RESULT_UPLOAD" \
    "src/inference -m e2e"

if [[ "$SURVIVORS" -gt 0 ]]; then
    echo "$SURVIVORS mutation(s) survived" >&2
    exit 1
fi

echo "All mutations caught"
