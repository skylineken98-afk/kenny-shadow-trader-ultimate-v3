"""Stable Railway entry point. Set WORKER_ROLE=news, scan, or orchestrator."""
import os
from workers.runner import main
if __name__ == '__main__':
    main(os.getenv('WORKER_ROLE','orchestrator'))
