"""
Train and Export Lightweight Biomechanical Keystroke Dynamics Regressor to ONNX.
Predicts (Dwell Time ms, Flight Time ms) based on key distance, modifiers, punctuation, and speed scale.
"""

import os
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType


def build_keystroke_training_data(n_samples: int = 4000) -> tuple[np.ndarray, np.ndarray]:
    """
    Synthesizes realistic human keystroke timing distributions:
    Features X:
    - 0: Key distance (0.0 to 9.0)
    - 1: Is Upper / Shift (0.0 or 1.0)
    - 2: Is Space (0.0 or 1.0)
    - 3: Is Punctuation (0.0 or 1.0)
    - 4: Speed scale (0.7 to 1.5)
    - 5: Fatigue factor (0.0 to 1.0)

    Targets y:
    - 0: Dwell time in ms (typically 45ms to 125ms)
    - 1: Flight time in ms (typically 40ms to 320ms)
    """
    np.random.seed(42)

    X = []
    y = []

    for _ in range(n_samples):
        dist = np.random.uniform(0.0, 7.5)
        is_upper = 1.0 if np.random.random() < 0.15 else 0.0
        is_space = 1.0 if np.random.random() < 0.18 else 0.0
        is_punct = 1.0 if np.random.random() < 0.10 else 0.0
        speed_scale = np.random.choice([0.75, 1.0, 1.25, 1.45])
        fatigue = np.random.uniform(0.0, 1.0)

        # Baseline human dwell time (ms)
        base_dwell = 65.0 * speed_scale
        if is_upper:
            base_dwell += 22.0
        if is_space:
            base_dwell += 14.0
        dwell = np.random.normal(base_dwell, 9.0)
        dwell = max(35.0, min(160.0, dwell))

        # Baseline human flight time (ms)
        base_flight = (70.0 + dist * 18.0) * speed_scale
        if is_upper:
            base_flight += 75.0
        if is_punct:
            base_flight += 85.0
        if is_space:
            base_flight += 38.0
        base_flight += fatigue * 24.0

        flight = np.random.normal(base_flight, 22.0)
        flight = max(25.0, min(500.0, flight))

        X.append([dist, is_upper, is_space, is_punct, speed_scale, fatigue])
        y.append([dwell, flight])

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_dir = os.path.join(base_dir, "models")
    os.makedirs(models_dir, exist_ok=True)

    print("Synthesizing keystroke biometrics dataset...")
    X, y = build_keystroke_training_data()

    print(f"Fitting Multi-Output Regressor on {len(X)} biometry vectors...")
    rf = RandomForestRegressor(
        n_estimators=45,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )
    rf.fit(X, y)

    initial_type = [('keystroke_input', FloatTensorType([None, 6]))]
    onnx_model = convert_sklearn(
        rf,
        initial_types=initial_type,
        target_opset={'': 14, 'ai.onnx.ml': 3}
    )

    out_path = os.path.join(models_dir, "keystroke_dynamics_v1.onnx")
    with open(out_path, "wb") as f:
        f.write(onnx_model.SerializeToString())

    print(f"Successfully exported Keystroke Dynamics ONNX model to: {out_path} ({os.path.getsize(out_path)} bytes)")


if __name__ == "__main__":
    main()
