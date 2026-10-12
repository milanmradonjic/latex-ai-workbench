"""Cheap checks: model limits, and when a result exists, that it came from the current parameters."""
import json
import math
from pathlib import Path

from decay import integrate


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


_, static = integrate(0, 2, 3, 20)
require(all(value == 2 for value in static), "Zero-rate limit failed")
errors = []
for steps in (20, 40):
    time, amplitude = integrate(1.5, 1, 3, steps)
    require(amplitude[0] == 1, "Initial condition failed")
    require(all(0 < after <= before for before, after in zip(amplitude, amplitude[1:])), "Positive monotonic decay failed")
    errors.append(max(abs(a - math.exp(-1.5 * t)) for t, a in zip(time, amplitude)))
require(errors[1] < errors[0] / 12, "Expected fourth-order convergence failed")
require(errors[1] < 1e-6, "Analytic absolute-error tolerance failed")
# Attribution: file timestamps cannot show that a result was derived from these parameters.
result = Path("results/decay.json")
if result.exists():
    parameters = json.loads(Path("parameters.json").read_text())
    stored = json.loads(result.read_text())
    require(stored.get("resolved_parameters") == parameters, "results/decay.json was not produced from the current parameters.json")
    gamma, initial = parameters["gamma"], parameters["initial"]
    require(max(abs(a - initial * math.exp(-gamma * t)) for t, a in zip(stored["time"], stored["amplitude"])) < 1e-6,
            "Stored samples disagree with the analytic solution for the current parameters")
print("Synthetic decay checks passed: zero-rate limit, positivity, monotonicity, convergence, analytic tolerance")
