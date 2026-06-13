"""api — FastAPI async turn endpoint serving the orchestrator (docs/01, docs/03).

`from carenav.api.app import app`; run with `uvicorn carenav.api.app:app`.
"""

from carenav.api.app import app

__all__ = ["app"]
