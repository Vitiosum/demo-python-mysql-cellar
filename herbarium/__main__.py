"""Start the web server: `python -m herbarium` (this is the Clever Cloud run command)."""

import logging
import os

import uvicorn

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    uvicorn.run(
        "herbarium.main:app",
        host="0.0.0.0",  # Clever Cloud checks that port 8080 listens publicly
        port=int(os.environ.get("PORT", "8080")),
        proxy_headers=True,  # trust X-Forwarded-* from the Clever Cloud load balancers
        forwarded_allow_ips="*",
    )
