"""Safe V3 local/worker readiness report. Never prints API key values."""
import json
from core.v3_readiness import audit
if __name__=='__main__':print(json.dumps(audit(),indent=2))
