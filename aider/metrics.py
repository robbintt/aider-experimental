try:
    from prometheus_client import Counter, Histogram

    prometheus_client_available = True
except ImportError:
    prometheus_client_available = False


if prometheus_client_available:
    # LLM Requests Total
    LLM_REQUESTS_TOTAL = Counter(
        "llm_requests_total",
        "Total number of LLM requests",
        ["model", "status"],
    )

    # LLM Request Duration
    LLM_REQUEST_DURATION_SECONDS = Histogram(
        "llm_request_duration_seconds",
        "LLM request duration in seconds",
        ["model"],
    )

    # Token Counts
    LLM_PROMPT_TOKENS_TOTAL = Counter(
        "llm_prompt_tokens_total",
        "Total number of prompt tokens",
        ["model"],
    )
    LLM_COMPLETION_TOKENS_TOTAL = Counter(
        "llm_completion_tokens_total",
        "Total number of completion tokens",
        ["model"],
    )
    LLM_TOTAL_TOKENS_TOTAL = Counter(
        "llm_total_tokens_total",
        "Total number of tokens",
        ["model"],
    )

    # Estimated Cost
    LLM_COST_USD_TOTAL = Counter(
        "llm_cost_usd_total",
        "Estimated cost of LLM requests in USD",
        ["model"],
    )


def success_callback(kwargs, completion_response, start_time, end_time):
    if not prometheus_client_available:
        return

    model = kwargs.get("model", "unknown")
    status = "success"
    duration = (end_time - start_time).total_seconds()

    LLM_REQUESTS_TOTAL.labels(model=model, status=status).inc()
    LLM_REQUEST_DURATION_SECONDS.labels(model=model).observe(duration)

    usage = completion_response.get("usage")
    if usage:
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        LLM_PROMPT_TOKENS_TOTAL.labels(model=model).inc(prompt_tokens)
        LLM_COMPLETION_TOKENS_TOTAL.labels(model=model).inc(completion_tokens)
        LLM_TOTAL_TOKENS_TOTAL.labels(model=model).inc(total_tokens)

    cost = completion_response.get("response_cost")
    if cost:
        LLM_COST_USD_TOTAL.labels(model=model).inc(cost)


def failure_callback(kwargs, completion_response, start_time, end_time):
    if not prometheus_client_available:
        return

    model = kwargs.get("model", "unknown")
    status = "failure"
    duration = (end_time - start_time).total_seconds()

    LLM_REQUESTS_TOTAL.labels(model=model, status=status).inc()
    LLM_REQUEST_DURATION_SECONDS.labels(model=model).observe(duration)
