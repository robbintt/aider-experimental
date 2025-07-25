# Prometheus Metrics Feature

This document outlines the steps to add Prometheus metrics to the `aider` application. Each step is designed to be a buildable and completable unit of work.

- [x] **1. Add `prometheus-client` as an optional dependency:**
    - Add `prometheus-client` to `requirements/requirements.in`.
    - In `pyproject.toml`, define a new optional dependency group named `metrics` that includes `prometheus-client`.

- [x] **2. Create the core metrics module:**
    - Create a new file named `aider/metrics.py`.
    - In this file, define the following Prometheus metrics, guarded by a `try...except ImportError` block for `prometheus-client`:
        - A `Counter` for total LLM requests, with labels for `model` and `status` (success/failure).
        - A `Histogram` for LLM request duration in seconds, with a label for `model`.
        - `Counter`s for total prompt, completion, and total tokens, each with a label for `model`.
        - A `Counter` for the estimated cost in USD, with a label for `model`.
    - Implement `litellm` callback functions (`success_callback` and `failure_callback`) that update these metrics.
        - The `success_callback` will receive `kwargs` and `completion_response` from `litellm` to extract model name, token usage, cost, and latency.
        - The `failure_callback` will receive the `exception` to log failed requests.
    - All code in this file should be structured to ensure `aider` can run without `prometheus-client` installed if the metrics feature is not used.

- [ ] **3. Register the metrics callbacks with `litellm`:**
    - In `aider/llm.py`, modify the `_load_litellm` method to register the success and failure callbacks from `aider/metrics.py`.
    - The registration should be wrapped in a `try...except` block to gracefully handle cases where the `prometheus-client` library is not installed.

- [ ] **4. Expose the metrics via command-line arguments:**
    - In `aider/main.py`, add new command-line arguments `--metrics-port` to specify the port and `--metrics-host` to specify the host for the metrics server (defaulting to `localhost`). These will be configurable in `.aider.conf.yml`.
    - In the `main` function, check if the `--metrics-port` argument is provided. If it is, start the Prometheus HTTP server in a background thread using the provided host and port.
    - Ensure this functionality is also wrapped in a `try...except ImportError` block and informs the user if the feature is used without the necessary dependency installed.
