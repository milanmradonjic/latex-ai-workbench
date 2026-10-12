"""Synthetic deterministic fixture: classical RK4 for scalar exponential decay."""
import json
from pathlib import Path


def integrate(gamma, initial, duration, steps):
    if gamma < 0 or duration < 0 or steps < 1:
        raise ValueError("Expected nonnegative rate/time and positive steps")
    dt = duration / steps
    values = [initial]
    for _ in range(steps):
        a = values[-1]
        k1 = -gamma * a
        k2 = -gamma * (a + dt * k1 / 2)
        k3 = -gamma * (a + dt * k2 / 2)
        k4 = -gamma * (a + dt * k3)
        values.append(a + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6)
    return [i * dt for i in range(steps + 1)], values


if __name__ == "__main__":
    config = json.loads(Path("parameters.json").read_text())
    time, amplitude = integrate(config["gamma"], config["initial"], config["duration"], config["steps"])
    result = {"synthetic": True, "resolved_parameters": config, "time": time, "amplitude": amplitude}
    Path("results").mkdir(exist_ok=True)
    Path("results/decay.json").write_text(json.dumps(result, indent=2) + "\n")
