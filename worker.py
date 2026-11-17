"""Stable Railway entry point. Set WORKER_ROLE=news, scan, or orchestrator."""
import os
from workers.runner import main
if __name__ == '__main__':
    role=os.getenv('WORKER_ROLE','orchestrator')
    if role=='momentum_alerts':
        from kst_options.momentum_alert_worker import main as alert_main
        alert_main()
    else:
        main(role)
