"""
Train and Export Lightweight Isolation Forest Fingerprint Anomaly Detector to ONNX.
"""

import os
import numpy as np
from sklearn.ensemble import IsolationForest
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

def build_training_data():
    """
    Synthesizes normalized feature vectors representing:
    - 0: OS (0=Win, 1=Mac, 2=Linux, 3=Android, 4=iOS)
    - 1: Browser Ver (normalized, e.g. 130 -> 1.30)
    - 2: WebGL Vendor (0=NVIDIA, 1=AMD, 2=Intel, 3=Apple, 4=Qualcomm/ARM, 5=Mesa)
    - 3: WebGL Renderer Match (1.0=matched OS, 0.0=mismatch)
    - 4: CPU Cores (e.g. 2, 4, 8, 12, 16, 24, 32)
    - 5: RAM GB (e.g. 4, 8, 16, 32, 64)
    - 6: Core/RAM Harmony (1.0=realistic, 0.0=unrealistic)
    - 7: Screen Aspect (1.0=standard landscape/portrait for OS, 0.0=mismatch)
    - 8: WebGPU (1.0=supported, 0.0=no)
    - 9: Canvas Noise (1.0=active, 0.0=off)
    - 10: Audio Noise (1.0=active, 0.0=off)
    - 11: WebRTC Altered (1.0=yes, 0.0=raw leak)
    """
    np.random.seed(42)
    normal_samples = []

    # Windows legitimate samples
    for _ in range(500):
        os_idx = 0.0
        b_ver = np.random.uniform(1.24, 1.35)
        vendor = np.random.choice([0.0, 1.0, 2.0])
        match = 1.0
        cores = float(np.random.choice([4, 6, 8, 12, 16]))
        ram = float(np.random.choice([8, 16, 32]))
        harmony = 1.0
        aspect = 1.0
        webgpu = float(np.random.choice([0.0, 1.0]))
        c_noise = 1.0
        a_noise = 1.0
        webrtc = 1.0
        normal_samples.append([os_idx, b_ver, vendor, match, cores, ram, harmony, aspect, webgpu, c_noise, a_noise, webrtc])

    # Mac legitimate samples
    for _ in range(400):
        os_idx = 1.0
        b_ver = np.random.uniform(1.24, 1.35)
        vendor = 3.0
        match = 1.0
        cores = float(np.random.choice([8, 10, 12, 16]))
        ram = float(np.random.choice([8, 16, 24, 32, 64]))
        harmony = 1.0
        aspect = 1.0
        webgpu = 1.0
        c_noise = 1.0
        a_noise = 1.0
        webrtc = 1.0
        normal_samples.append([os_idx, b_ver, vendor, match, cores, ram, harmony, aspect, webgpu, c_noise, a_noise, webrtc])

    # Linux legitimate samples
    for _ in range(250):
        os_idx = 2.0
        b_ver = np.random.uniform(1.24, 1.35)
        vendor = np.random.choice([0.0, 1.0, 2.0, 5.0])
        match = 1.0
        cores = float(np.random.choice([4, 8, 16, 32]))
        ram = float(np.random.choice([8, 16, 32, 64]))
        harmony = 1.0
        aspect = 1.0
        webgpu = float(np.random.choice([0.0, 1.0]))
        c_noise = 1.0
        a_noise = 1.0
        webrtc = 1.0
        normal_samples.append([os_idx, b_ver, vendor, match, cores, ram, harmony, aspect, webgpu, c_noise, a_noise, webrtc])

    X = np.array(normal_samples, dtype=np.float32)
    return X


from sklearn.ensemble import RandomForestRegressor


def build_mouse_trajectory_training_data():
    """
    Synthesizes biomechanical mouse movement curves following minimum-jerk equations
    with physiological micro-tremor and sub-movement ballistic profiles.
    Inputs (8 features):
    - 0: start_x / 1920
    - 1: start_y / 1080
    - 2: target_x / 1920
    - 3: target_y / 1080
    - 4: progress_t (0.0 to 1.0)
    - 5: normalized_dist (distance / 2000)
    - 6: duration (sec)
    - 7: speed_factor
    Outputs (4 targets):
    - step_dx, step_dy, tremor_x, tremor_y
    """
    np.random.seed(1337)
    X_samples = []
    y_samples = []

    for _ in range(1200):
        sx, sy = np.random.uniform(50, 1850), np.random.uniform(50, 1000)
        tx, ty = np.random.uniform(50, 1850), np.random.uniform(50, 1000)
        dist = np.hypot(tx - sx, ty - sy)
        duration = max(0.15, 0.12 + 0.15 * np.log2(1 + dist / 40.0))
        speed_factor = np.random.uniform(0.85, 1.25)

        num_steps = 30
        for step in range(num_steps):
            t = step / float(num_steps - 1)
            # Minimum-jerk polynomial trajectory profile: 10t^3 - 15t^4 + 6t^5
            poly = 10 * (t ** 3) - 15 * (t ** 4) + 6 * (t ** 5)
            curr_x = sx + (tx - sx) * poly
            curr_y = sy + (ty - sy) * poly

            tremor_x = np.random.normal(0.0, 0.4)
            tremor_y = np.random.normal(0.0, 0.4)

            next_t = min(1.0, (step + 1) / float(num_steps - 1))
            next_poly = 10 * (next_t ** 3) - 15 * (next_t ** 4) + 6 * (next_t ** 5)
            next_x = sx + (tx - sx) * next_poly
            next_y = sy + (ty - sy) * next_poly

            step_dx = next_x - curr_x
            step_dy = next_y - curr_y

            feat = [
                sx / 1920.0, sy / 1080.0,
                tx / 1920.0, ty / 1080.0,
                t, dist / 2000.0, duration, speed_factor
            ]
            target = [step_dx, step_dy, tremor_x, tremor_y]
            X_samples.append(feat)
            y_samples.append(target)

    return np.array(X_samples, dtype=np.float32), np.array(y_samples, dtype=np.float32)


def train_mouse_trajectory_model(models_dir: str):
    """Trains and exports the Biomechanical Mouse Trajectory CNN/Regressor to ONNX format."""
    print("Synthesizing biomechanical human motor trajectory training set...")
    X_traj, y_traj = build_mouse_trajectory_training_data()
    print(f"Training Random Forest Trajectory Regressor on {len(X_traj)} path steps...")

    traj_rf = RandomForestRegressor(
        n_estimators=50,
        max_depth=12,
        random_state=42,
        n_jobs=-1
    )
    traj_rf.fit(X_traj, y_traj)

    initial_type = [('motion_input', FloatTensorType([None, 8]))]
    onnx_traj = convert_sklearn(
        traj_rf,
        initial_types=initial_type,
        target_opset={'': 14, 'ai.onnx.ml': 3}
    )

    traj_onnx_path = os.path.join(models_dir, "mouse_trajectory_v1.onnx")
    with open(traj_onnx_path, "wb") as f:
        f.write(onnx_traj.SerializeToString())

    print(f"Successfully exported Mouse Trajectory ONNX model to: {traj_onnx_path} ({os.path.getsize(traj_onnx_path)} bytes)")


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_dir = os.path.join(base_dir, "models")
    os.makedirs(models_dir, exist_ok=True)

    # 1. Isolation Forest Sentinel Model
    X = build_training_data()
    print(f"Training Isolation Forest on {len(X)} baseline fingerprint vectors...")

    model = IsolationForest(
        n_estimators=60,
        contamination=0.04,
        max_samples=256,
        random_state=42
    )
    model.fit(X)

    onnx_path = os.path.join(models_dir, "fingerprint_anomaly_v1.onnx")
    initial_type = [('float_input', FloatTensorType([None, 12]))]
    onnx_model = convert_sklearn(
        model,
        initial_types=initial_type,
        target_opset={'': 14, 'ai.onnx.ml': 3}
    )

    with open(onnx_path, "wb") as f:
        f.write(onnx_model.SerializeToString())

    print(f"Successfully exported Sentinel ONNX model to: {onnx_path} ({os.path.getsize(onnx_path)} bytes)")

    # 2. Mouse Trajectory Model
    train_mouse_trajectory_model(models_dir)


if __name__ == "__main__":
    main()
