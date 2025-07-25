# Prometheus Metrics Feature

This document outlines the steps to add Prometheus metrics to the `aider` application. Each step is designed to be a buildable and completable unit of work.

- [ ] **1. Add `prometheus-client` as an optional dependency:**
    - Add `prometheus-client` to `requirements/requirements.in`.
    - In `pyproject.toml`, define a new optional dependency group named `metrics` that includes `prometheus-client`.

- [ ] **2. Create the core metrics module:**
    - Create a new file named `aider/metrics.py`.
    - In this file, define the Prometheus metrics (Counters and Histograms) for tracking LLM requests, token usage, and latency.
    - Implement the `litellm` callback functions (`success_callback` and `failure_callback`) that will update these metrics. All code in this file that depends on `prometheus-client` should be guarded by a `try...except ImportError` block to ensure it remains an optional feature.

- [ ] **3. Register the metrics callbacks with `litellm`:**
    - In `aider/llm.py`, modify the `_load_litellm` method to register the success and failure callbacks from `aider/metrics.py`.
    - The registration should be wrapped in a `try...except` block to gracefully handle cases where the `prometheus-client` library is not installed.

- [ ] **4. Expose the metrics via a command-line argument:**
    - In `aider/main.py`, add a new command-line argument `--metrics-port` to specify the port for the metrics server.
    - In the `main` function, check if the `--metrics-port` argument is provided. If it is, start the Prometheus HTTP server in a background thread.
    - Ensure this functionality is also wrapped in a `try...except ImportError` block and informs the user if the feature is used without the necessary dependency installed.
