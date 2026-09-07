import os
import json
import uuid
import time
import asyncio
import logging
from collections import deque
from typing import Dict, Any, List, Optional, Tuple

import config
from engine.workflow_engine import WorkflowDAG, MultiWorkflowRunner, WorkflowExecutionState
from engine.events import AsyncEventBus

logger = logging.getLogger("WorkflowService")


class WorkflowExecutionService:
    """
    Headless Orchestration & Execution Service for Visual DAG Workflows.
    Bridges REST API endpoints and headless automations with MultiWorkflowRunner.
    """
    _instance: Optional['WorkflowExecutionService'] = None

    def __init__(self, workflows_dir: Optional[str] = None):
        self.workflows_dir = workflows_dir or os.path.join(config.BASE_DIR, "storage", "workflows")
        os.makedirs(self.workflows_dir, exist_ok=True)
        self.executions: Dict[str, Dict[str, Any]] = {}
        self.active_runners: Dict[str, MultiWorkflowRunner] = {}

    @classmethod
    def get_instance(cls) -> 'WorkflowExecutionService':
        if cls._instance is None:
            cls._instance = WorkflowExecutionService()
        return cls._instance

    def list_workflows(self) -> List[Dict[str, Any]]:
        """Scans storage/workflows/*.json and returns catalog summaries."""
        results = []
        if not os.path.isdir(self.workflows_dir):
            return results

        for fname in sorted(os.listdir(self.workflows_dir)):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self.workflows_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                nodes_count = len(data.get("nodes", {}))
                results.append({
                    "id": data.get("id") or fname[:-5],
                    "file_name": fname,
                    "name": data.get("name", fname[:-5]),
                    "description": data.get("description", ""),
                    "category": data.get("category", "General"),
                    "nodes_count": nodes_count,
                    "updated_at": data.get("updated_at", os.path.getmtime(fpath))
                })
            except Exception as e:
                logger.debug(f"[WorkflowService] Could not parse workflow file {fname}: {e}")
        return results

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Loads full workflow definition by ID or filename."""
        if not os.path.isdir(self.workflows_dir):
            return None

        # Direct file check
        candidate_path = os.path.join(self.workflows_dir, f"{workflow_id}.json" if not workflow_id.endswith(".json") else workflow_id)
        if os.path.exists(candidate_path):
            try:
                with open(candidate_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Scan for ID inside JSON
        for fname in os.listdir(self.workflows_dir):
            if fname.endswith(".json"):
                fpath = os.path.join(self.workflows_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("id") == workflow_id or fname[:-5] == workflow_id:
                        return data
                except Exception:
                    pass
        return None

    async def start_workflow(
        self,
        workflow_id_or_dict: Any,
        profile_ids: List[str],
        launcher: Any,
        concurrency: int = 4,
        variables: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Launches a headless workflow run across one or multiple profiles concurrently.
        Returns: (success: bool, message: str, execution_id: Optional[str])
        """
        if not profile_ids:
            return False, "No profile IDs provided for workflow execution.", None

        # Resolve DAG data
        if isinstance(workflow_id_or_dict, dict):
            dag_data = workflow_id_or_dict
        elif isinstance(workflow_id_or_dict, str):
            dag_data = self.get_workflow(workflow_id_or_dict)
            if not dag_data:
                return False, f"Workflow '{workflow_id_or_dict}' not found.", None
        else:
            return False, "Invalid workflow specification.", None

        try:
            dag = WorkflowDAG.from_dict(dag_data)
        except Exception as e:
            return False, f"Failed to construct Workflow DAG: {e}", None

        # Merge runtime variable overrides
        if variables and isinstance(variables, dict):
            dag.variables.update(variables)

        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        runner = MultiWorkflowRunner(dag, profile_ids=profile_ids, max_concurrency=concurrency)
        self.active_runners[execution_id] = runner

        execution_record: Dict[str, Any] = {
            "execution_id": execution_id,
            "workflow_id": dag.id,
            "workflow_name": dag.name,
            "profile_ids": list(profile_ids),
            "concurrency": concurrency,
            "status": "running",
            "progress_pct": 0.0,
            "profile_statuses": {pid: {"status": "queued", "current_node": None, "progress_pct": 0.0} for pid in profile_ids},
            "recent_logs": deque(maxlen=300),
            "results": {},
            "start_time": time.time(),
            "end_time": None
        }
        self.executions[execution_id] = execution_record

        # Define callbacks for runner telemetry
        def log_cb(msg: str):
            ts_str = time.strftime("%H:%M:%S")
            line = f"[{ts_str}] {msg}"
            execution_record["recent_logs"].append(line)
            AsyncEventBus.get_instance().emit_sync("workflow_log", payload={
                "execution_id": execution_id,
                "message": line
            })

        def profile_status_cb(pid: str, st: str, node_title: Optional[str], pct: float):
            p_stat = execution_record["profile_statuses"].get(pid, {})
            p_stat["status"] = st
            p_stat["current_node"] = node_title
            p_stat["progress_pct"] = round(pct, 2)
            execution_record["profile_statuses"][pid] = p_stat

            # Calculate aggregated progress percentage
            all_pcts = [p.get("progress_pct", 0.0) for p in execution_record["profile_statuses"].values()]
            if all_pcts:
                execution_record["progress_pct"] = round(sum(all_pcts) / len(all_pcts), 1)

            AsyncEventBus.get_instance().emit_sync("workflow_progress", payload={
                "execution_id": execution_id,
                "profile_id": pid,
                "status": st,
                "node_title": node_title,
                "progress_pct": pct,
                "total_progress": execution_record["progress_pct"]
            })

        async def _execute_task():
            try:
                res = await runner.execute(
                    launcher=launcher,
                    in_browser=True,
                    log_cb=log_cb,
                    profile_status_cb=profile_status_cb
                )
                execution_record["results"] = res
                execution_record["status"] = "completed" if runner.state != WorkflowExecutionState.STOPPED else "stopped"
                execution_record["progress_pct"] = 100.0 if execution_record["status"] == "completed" else execution_record["progress_pct"]
            except Exception as e:
                logger.error(f"[WorkflowService] Execution '{execution_id}' exception: {e}", exc_info=True)
                execution_record["status"] = "failed"
                log_cb(f"❌ Execution failed: {e}")
            finally:
                execution_record["end_time"] = time.time()
                self.active_runners.pop(execution_id, None)
                AsyncEventBus.get_instance().emit_sync("workflow_completed", payload={
                    "execution_id": execution_id,
                    "status": execution_record["status"],
                    "duration_sec": round(execution_record["end_time"] - execution_record["start_time"], 1)
                })

        asyncio.create_task(_execute_task())
        logger.info(f"[WorkflowService] Started execution '{execution_id}' for workflow '{dag.name}' on {len(profile_ids)} profile(s)")
        return True, f"Workflow execution '{execution_id}' started.", execution_id

    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Returns structured status and logs for given execution ID."""
        rec = self.executions.get(execution_id)
        if not rec:
            return None
        return {
            "execution_id": rec["execution_id"],
            "workflow_id": rec["workflow_id"],
            "workflow_name": rec["workflow_name"],
            "profile_ids": rec["profile_ids"],
            "concurrency": rec["concurrency"],
            "status": rec["status"],
            "progress_pct": rec["progress_pct"],
            "profile_statuses": rec["profile_statuses"],
            "recent_logs": list(rec["recent_logs"])[-50:],
            "results": rec.get("results", {}),
            "start_time": rec["start_time"],
            "end_time": rec["end_time"],
            "duration_sec": round((rec["end_time"] or time.time()) - rec["start_time"], 1)
        }

    def stop_execution(self, execution_id: str) -> bool:
        """Halts an active running workflow execution."""
        runner = self.active_runners.get(execution_id)
        if runner:
            runner.stop()
            rec = self.executions.get(execution_id)
            if rec:
                rec["status"] = "stopping"
            return True
        return False
