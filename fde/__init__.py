"""fde-delivery-engine: the delivery engine of a forward-deployed engineering team."""

import os

# Customer pipelines can run air-gapped: Haystack must not phone home.
os.environ.setdefault("HAYSTACK_TELEMETRY_ENABLED", "False")
