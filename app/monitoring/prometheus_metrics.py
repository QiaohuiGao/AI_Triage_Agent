from prometheus_client import Counter, Histogram
triage_latency = Histogram("triage_request_latency_seconds", "End-to-end triage request latency")
triage_success = Counter("triage_success_total", "Successful triage requests")
triage_errors = Counter("triage_errors_total", "Errors during triage processing")
