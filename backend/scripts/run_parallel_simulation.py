"""
OASIS dual-platform parallel simulation preset script.
Runs Twitter and Reddit simulations simultaneously from the same config file.

Features:
- Dual-platform (Twitter + Reddit) parallel simulation
- After simulation completes, stays alive waiting for IPC commands
- Supports Interview commands (single agent and batch) via IPC
- Supports remote close_env command

Usage:
    python run_parallel_simulation.py --config simulation_config.json
    python run_parallel_simulation.py --config simulation_config.json --no-wait
    python run_parallel_simulation.py --config simulation_config.json --twitter-only
    python run_parallel_simulation.py --config simulation_config.json --reddit-only

Log structure:
    sim_xxx/
    ├── twitter/
    │   └── actions.jsonl    # Twitter platform action log
    ├── reddit/
    │   └── actions.jsonl    # Reddit platform action log
    ├── simulation.log       # Main simulation process log
    └── run_state.json       # Run state (queried by API)
"""

# ============================================================
# Fix Windows encoding: set UTF-8 before all imports
# This fixes OASIS third-party libs that open files without specifying encoding
# ============================================================
import sys
import os

if sys.platform == 'win32':
    # Set Python default I/O encoding to UTF-8
    # Affects all open() calls that don't specify encoding
    os.environ.setdefault('PYTHONUTF8', '1')
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

    # Reconfigure stdout/stderr to UTF-8 (fixes console encoding on Windows)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    # Force default encoding (affects default encoding for open())
    # Note: this ideally should be set at Python startup; runtime changes may not fully apply
    # So we also monkey-patch the built-in open function
    import builtins
    _original_open = builtins.open

    def _utf8_open(file, mode='r', buffering=-1, encoding=None, errors=None,
                   newline=None, closefd=True, opener=None):
        """Wrap open() to default text-mode files to UTF-8 encoding.
        Fixes third-party libs (e.g. OASIS) that open files without specifying encoding.
        """
        # Only set default encoding for text mode (non-binary) when encoding is not specified
        if encoding is None and 'b' not in mode:
            encoding = 'utf-8'
        return _original_open(file, mode, buffering, encoding, errors,
                              newline, closefd, opener)

    builtins.open = _utf8_open

import argparse
import asyncio
import json
import logging
import multiprocessing
import random
import signal
import sqlite3
import warnings
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple


# Global variables for signal handling
_shutdown_event = None
_cleanup_done = False

# Add backend directory to path
# Script is always located in backend/scripts/
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_scripts_dir, '..'))
_project_root = os.path.abspath(os.path.join(_backend_dir, '..'))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, _backend_dir)

# Load .env from project root (contains LLM_API_KEY and other settings)
from dotenv import load_dotenv
_env_file = os.path.join(_project_root, '.env')
if os.path.exists(_env_file):
    load_dotenv(_env_file)
    print(f"Loaded env config: {_env_file}")
else:
    # Try loading backend/.env
    _backend_env = os.path.join(_backend_dir, '.env')
    if os.path.exists(_backend_env):
        load_dotenv(_backend_env)
        print(f"Loaded env config: {_backend_env}")


class MaxTokensWarningFilter(logging.Filter):
    """Filter out camel-ai warnings about max_tokens (we intentionally omit it, letting the model decide)."""

    def filter(self, record):
        # Filter log records containing max_tokens warnings
        if "max_tokens" in record.getMessage() and "Invalid or missing" in record.getMessage():
            return False
        return True


# Add filter at module load time, before any camel code executes
logging.getLogger().addFilter(MaxTokensWarningFilter())


def disable_oasis_logging():
    """
    Disable verbose OASIS library logging.
    OASIS logs every agent observation and action; we use our own action_logger instead.
    """
    # Disable all OASIS loggers
    oasis_loggers = [
        "social.agent",
        "social.twitter", 
        "social.rec",
        "oasis.env",
        "table",
    ]
    
    for logger_name in oasis_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL)
        logger.handlers.clear()
        logger.propagate = False


def init_logging_for_simulation(simulation_dir: str):
    """
    Initialize logging for simulation.

    Args:
        simulation_dir: Simulation directory path
    """
    # Disable OASIS verbose logging
    disable_oasis_logging()

    # Remove old log directory if present
    old_log_dir = os.path.join(simulation_dir, "log")
    if os.path.exists(old_log_dir):
        import shutil
        shutil.rmtree(old_log_dir, ignore_errors=True)


from action_logger import SimulationLogManager, PlatformActionLogger

try:
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType
    import oasis
    from oasis import (
        ActionType,
        LLMAction,
        ManualAction,
        generate_twitter_agent_graph,
        generate_reddit_agent_graph
    )
    from oasis.social_platform.platform import Platform as OasisPlatform
    from oasis.social_platform.channel import Channel as OasisChannel
except ImportError as e:
    print(f"Error: missing dependency {e}")
    print("Please install: pip install oasis-ai camel-ai")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Context compaction for SocialAgent
#
# Reddit agents accumulate very long conversation histories (each round adds
# the full social-media environment snapshot + tool results). By round ~44 with
# 89 agents the context can reach 1–1.7 M tokens, which exceeds gpt-5.1's
# 272k-token limit and crashes the simulation.
#
# Strategy: before every LLM call, count the tokens already in memory.  If
# they exceed COMPACTION_THRESHOLD, replace all but the system message with a
# single summary generated by LLM_SMALL.  The summary is prepended with a
# marker so the agent knows it is working from a condensed history.
#
# COMPACTION_THRESHOLD: when memory tokens exceed this value, compact.
# COMPACTION_TARGET   : target token budget for the summary itself.
# ─────────────────────────────────────────────────────────────────────────────
COMPACTION_THRESHOLD = int(os.environ.get("AGENT_COMPACTION_THRESHOLD", "80000"))
COMPACTION_TARGET    = int(os.environ.get("AGENT_COMPACTION_TARGET",    "40000"))


def _create_small_client():
    """Build an OpenAI-compatible client using LLM_SMALL_* env vars (or fall back to LLM_*)."""
    from openai import OpenAI as _OpenAI
    api_key  = os.environ.get("LLM_SMALL_API_KEY")  or os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_SMALL_BASE_URL")  or os.environ.get("LLM_BASE_URL", "")
    model    = os.environ.get("LLM_SMALL_MODEL_NAME") or os.environ.get("LLM_MODEL_NAME", "gpt-4o-mini")

    # For Azure URLs that include /openai/v1/ we can use them directly
    # For full Azure deployment URLs we strip to base endpoint
    if base_url and "cognitiveservices.azure.com" in base_url:
        # Keep as-is if it already ends at a v1 path; otherwise just use it
        if not base_url.rstrip("/").endswith("/v1"):
            # Try to use the services endpoint with /api/projects/.../openai/v1
            pass  # use base_url as provided
    return _OpenAI(api_key=api_key, base_url=base_url), model


_small_client = None
_small_model  = None


def _get_small_client():
    global _small_client, _small_model
    if _small_client is None:
        _small_client, _small_model = _create_small_client()
    return _small_client, _small_model


def _count_memory_tokens(agent) -> int:
    """Estimate the token count of messages currently in the agent's memory."""
    try:
        context_creator = agent.memory.get_context_creator()
        token_counter   = context_creator.token_counter
        messages, num_tokens = agent.memory.get_context()
        return num_tokens
    except Exception:
        return 0


def _compact_agent_memory(agent, platform_label: str = "") -> bool:
    """
    Summarise an agent's conversation history with LLM_SMALL and replace
    the history (excluding the system message) with the summary.

    Returns True if compaction was performed, False otherwise.
    """
    try:
        from camel.messages import BaseMessage
        from camel.types import OpenAIBackendRole
        from camel.memories.records import MemoryRecord

        storage = agent.memory._chat_history_block.storage
        all_records = storage.load()  # list of dicts

        if len(all_records) < 4:
            return False  # nothing worth compacting

        # Split: keep system/developer messages, compact the rest
        system_records = [
            r for r in all_records
            if r.get("role_at_backend") in (
                OpenAIBackendRole.SYSTEM.value,
                OpenAIBackendRole.DEVELOPER.value,
                "system", "developer",
            )
        ]
        history_records = [
            r for r in all_records
            if r.get("role_at_backend") not in (
                OpenAIBackendRole.SYSTEM.value,
                OpenAIBackendRole.DEVELOPER.value,
                "system", "developer",
            )
        ]

        if not history_records:
            return False

        # Build plain-text history for the summary prompt (cap at 200k chars)
        history_text = ""
        for r in history_records:
            msg = r.get("message", {})
            role    = r.get("role_at_backend", "user")
            content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
            history_text += f"[{role}]: {content}\n\n"
        history_text = history_text[-200_000:]  # keep tail (most recent)

        # Call LLM_SMALL for a condensed summary
        client, model = _get_small_client()
        summary_prompt = (
            "You are a memory compaction assistant. "
            "Below is a social-media simulation agent's conversation history. "
            "Summarise it concisely, preserving: the agent's identity, opinions, "
            "past actions (posts, likes, follows, comments), topics discussed, "
            "emotional tone, and any key relationships. "
            f"Keep the summary under {COMPACTION_TARGET // 4} words.\n\n"
            f"HISTORY:\n{history_text}"
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": summary_prompt}],
            max_completion_tokens=COMPACTION_TARGET // 4,
            temperature=0.3,
        )
        summary = response.choices[0].message.content.strip()

        # Build a synthetic "assistant" memory record with the summary
        summary_content = (
            f"[COMPACTED MEMORY — summary of {len(history_records)} prior turns]\n"
            f"{summary}"
        )
        summary_msg = BaseMessage.make_assistant_message(
            role_name="Assistant",
            content=summary_content,
        )
        summary_record = MemoryRecord(
            message=summary_msg,
            role_at_backend=OpenAIBackendRole.ASSISTANT,
        )

        # Replace storage: system messages + summary record
        new_records = system_records + [summary_record.to_dict()]
        storage.memory_list.clear()
        storage.memory_list.extend(new_records)

        agent_id = getattr(agent, 'social_agent_id', '?')
        print(f"  [{platform_label}] Agent {agent_id}: memory compacted "
              f"({len(history_records)} turns → 1 summary)", flush=True)
        return True

    except Exception as e:
        agent_id = getattr(agent, 'social_agent_id', '?')
        print(f"  [{platform_label}] Agent {agent_id}: compaction failed: {e}", flush=True)
        return False


_compaction_patch_applied = False


def _patch_social_agent_compaction(platform_label: str):
    """
    Monkey-patch SocialAgent.perform_action_by_llm to inject context
    compaction before every LLM call.  Idempotent — safe to call twice.
    """
    global _compaction_patch_applied
    if _compaction_patch_applied:
        return
    _compaction_patch_applied = True

    from oasis.social_agent.agent import SocialAgent

    _original_perform = SocialAgent.perform_action_by_llm

    async def _perform_with_compaction(self):
        tokens = _count_memory_tokens(self)
        if tokens > COMPACTION_THRESHOLD:
            _compact_agent_memory(self, getattr(self, '_platform_label', 'Agent'))
        return await _original_perform(self)

    SocialAgent.perform_action_by_llm = _perform_with_compaction


# Available Twitter actions (INTERVIEW excluded — must be triggered via ManualAction)
TWITTER_ACTIONS = [
    ActionType.CREATE_POST,
    ActionType.LIKE_POST,
    ActionType.REPOST,
    ActionType.FOLLOW,
    ActionType.DO_NOTHING,
    ActionType.QUOTE_POST,
]

# Available Reddit actions (INTERVIEW excluded — must be triggered via ManualAction)
REDDIT_ACTIONS = [
    ActionType.LIKE_POST,
    ActionType.DISLIKE_POST,
    ActionType.CREATE_POST,
    ActionType.CREATE_COMMENT,
    ActionType.LIKE_COMMENT,
    ActionType.DISLIKE_COMMENT,
    ActionType.SEARCH_POSTS,
    ActionType.SEARCH_USER,
    ActionType.TREND,
    ActionType.REFRESH,
    ActionType.DO_NOTHING,
    ActionType.FOLLOW,
    ActionType.MUTE,
]


# IPC constants
IPC_COMMANDS_DIR = "ipc_commands"
IPC_RESPONSES_DIR = "ipc_responses"
ENV_STATUS_FILE = "env_status.json"

class CommandType:
    """Command type constants."""
    INTERVIEW = "interview"
    BATCH_INTERVIEW = "batch_interview"
    CLOSE_ENV = "close_env"


class ParallelIPCHandler:
    """
    Dual-platform IPC command handler.

    Manages environments for both platforms and handles Interview commands.
    """
    
    def __init__(
        self,
        simulation_dir: str,
        twitter_env=None,
        twitter_agent_graph=None,
        reddit_env=None,
        reddit_agent_graph=None
    ):
        self.simulation_dir = simulation_dir
        self.twitter_env = twitter_env
        self.twitter_agent_graph = twitter_agent_graph
        self.reddit_env = reddit_env
        self.reddit_agent_graph = reddit_agent_graph
        
        self.commands_dir = os.path.join(simulation_dir, IPC_COMMANDS_DIR)
        self.responses_dir = os.path.join(simulation_dir, IPC_RESPONSES_DIR)
        self.status_file = os.path.join(simulation_dir, ENV_STATUS_FILE)
        
        # Ensure directories exist
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
    
    def update_status(self, status: str):
        """Update environment status."""
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump({
                "status": status,
                "twitter_available": self.twitter_env is not None,
                "reddit_available": self.reddit_env is not None,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def poll_command(self) -> Optional[Dict[str, Any]]:
        """Poll for a pending command."""
        if not os.path.exists(self.commands_dir):
            return None

        # Get command files sorted by modification time
        command_files = []
        for filename in os.listdir(self.commands_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.commands_dir, filename)
                command_files.append((filepath, os.path.getmtime(filepath)))
        
        command_files.sort(key=lambda x: x[1])
        
        for filepath, _ in command_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
        
        return None
    
    def send_response(self, command_id: str, status: str, result: Dict = None, error: str = None):
        """Send a response."""
        response = {
            "command_id": command_id,
            "status": status,
            "result": result,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        
        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response, f, ensure_ascii=False, indent=2)
        
        # Delete the command file
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass
    
    def _get_env_and_graph(self, platform: str):
        """
        Return (env, agent_graph, platform_name) for the given platform, or (None, None, None).

        Args:
            platform: Platform name ("twitter" or "reddit")
        """
        if platform == "twitter" and self.twitter_env:
            return self.twitter_env, self.twitter_agent_graph, "twitter"
        elif platform == "reddit" and self.reddit_env:
            return self.reddit_env, self.reddit_agent_graph, "reddit"
        else:
            return None, None, None
    
    async def _interview_single_platform(self, agent_id: int, prompt: str, platform: str) -> Dict[str, Any]:
        """
        Run an Interview on a single platform.

        Returns:
            Dict with result data, or a dict with an "error" key.
        """
        env, agent_graph, actual_platform = self._get_env_and_graph(platform)
        
        if not env or not agent_graph:
            return {"platform": platform, "error": f"{platform} platform unavailable"}
        
        try:
            agent = agent_graph.get_agent(agent_id)
            interview_action = ManualAction(
                action_type=ActionType.INTERVIEW,
                action_args={"prompt": prompt}
            )
            actions = {agent: interview_action}
            await env.step(actions)
            
            result = self._get_interview_result(agent_id, actual_platform)
            result["platform"] = actual_platform
            return result
            
        except Exception as e:
            return {"platform": platform, "error": str(e)}
    
    async def handle_interview(self, command_id: str, agent_id: int, prompt: str, platform: str = None) -> bool:
        """
        Handle a single-agent interview command.

        Args:
            command_id: Command ID
            agent_id: Agent ID
            prompt: Interview question
            platform: Target platform (optional)
                - "twitter": interview on Twitter only
                - "reddit": interview on Reddit only
                - None: interview on both platforms simultaneously

        Returns:
            True on success, False on failure.
        """
        # If a specific platform was requested, interview only that one
        if platform in ("twitter", "reddit"):
            result = await self._interview_single_platform(agent_id, prompt, platform)
            
            if "error" in result:
                self.send_response(command_id, "failed", error=result["error"])
                print(f"  Interview failed: agent_id={agent_id}, platform={platform}, error={result['error']}")
                return False
            else:
                self.send_response(command_id, "completed", result=result)
                print(f"  Interview done: agent_id={agent_id}, platform={platform}")
                return True
        
        # No platform specified: interview both simultaneously
        if not self.twitter_env and not self.reddit_env:
            self.send_response(command_id, "failed", error="No simulation environment available")
            return False
        
        results = {
            "agent_id": agent_id,
            "prompt": prompt,
            "platforms": {}
        }
        success_count = 0
        
        # Interview both platforms in parallel
        tasks = []
        platforms_to_interview = []
        
        if self.twitter_env:
            tasks.append(self._interview_single_platform(agent_id, prompt, "twitter"))
            platforms_to_interview.append("twitter")
        
        if self.reddit_env:
            tasks.append(self._interview_single_platform(agent_id, prompt, "reddit"))
            platforms_to_interview.append("reddit")
        
        # Run concurrently
        platform_results = await asyncio.gather(*tasks)
        
        for platform_name, platform_result in zip(platforms_to_interview, platform_results):
            results["platforms"][platform_name] = platform_result
            if "error" not in platform_result:
                success_count += 1
        
        if success_count > 0:
            self.send_response(command_id, "completed", result=results)
            print(f"  Interview done: agent_id={agent_id}, successful platforms={success_count}/{len(platforms_to_interview)}")
            return True
        else:
            errors = [f"{p}: {r.get('error', 'unknown error')}" for p, r in results["platforms"].items()]
            self.send_response(command_id, "failed", error="; ".join(errors))
            print(f"  Interview failed: agent_id={agent_id}, all platforms failed")
            return False
    
    async def handle_batch_interview(self, command_id: str, interviews: List[Dict], platform: str = None) -> bool:
        """
        Handle a batch interview command.

        Args:
            command_id: Command ID
            interviews: [{"agent_id": int, "prompt": str, "platform": str(optional)}, ...]
            platform: Default platform (can be overridden per interview item)
                - "twitter": Twitter only
                - "reddit": Reddit only
                - None: interview on both platforms per agent
        """
        # Group interviews by platform
        twitter_interviews = []
        reddit_interviews = []
        both_platforms_interviews = []  # interviews that need both platforms
        
        for interview in interviews:
            item_platform = interview.get("platform", platform)
            if item_platform == "twitter":
                twitter_interviews.append(interview)
            elif item_platform == "reddit":
                reddit_interviews.append(interview)
            else:
                # No platform specified: interview on both
                both_platforms_interviews.append(interview)

        # Distribute both-platform interviews to each platform list
        if both_platforms_interviews:
            if self.twitter_env:
                twitter_interviews.extend(both_platforms_interviews)
            if self.reddit_env:
                reddit_interviews.extend(both_platforms_interviews)
        
        results = {}
        
        # Process Twitter platform interviews
        if twitter_interviews and self.twitter_env:
            try:
                twitter_actions = {}
                for interview in twitter_interviews:
                    agent_id = interview.get("agent_id")
                    prompt = interview.get("prompt", "")
                    try:
                        agent = self.twitter_agent_graph.get_agent(agent_id)
                        twitter_actions[agent] = ManualAction(
                            action_type=ActionType.INTERVIEW,
                            action_args={"prompt": prompt}
                        )
                    except Exception as e:
                        print(f"  Warning: cannot get Twitter Agent {agent_id}: {e}")
                
                if twitter_actions:
                    await self.twitter_env.step(twitter_actions)
                    
                    for interview in twitter_interviews:
                        agent_id = interview.get("agent_id")
                        result = self._get_interview_result(agent_id, "twitter")
                        result["platform"] = "twitter"
                        results[f"twitter_{agent_id}"] = result
            except Exception as e:
                print(f"  Twitter batch interview failed: {e}")
        
        # Process Reddit platform interviews
        if reddit_interviews and self.reddit_env:
            try:
                reddit_actions = {}
                for interview in reddit_interviews:
                    agent_id = interview.get("agent_id")
                    prompt = interview.get("prompt", "")
                    try:
                        agent = self.reddit_agent_graph.get_agent(agent_id)
                        reddit_actions[agent] = ManualAction(
                            action_type=ActionType.INTERVIEW,
                            action_args={"prompt": prompt}
                        )
                    except Exception as e:
                        print(f"  Warning: cannot get Reddit Agent {agent_id}: {e}")
                
                if reddit_actions:
                    await self.reddit_env.step(reddit_actions)
                    
                    for interview in reddit_interviews:
                        agent_id = interview.get("agent_id")
                        result = self._get_interview_result(agent_id, "reddit")
                        result["platform"] = "reddit"
                        results[f"reddit_{agent_id}"] = result
            except Exception as e:
                print(f"  Reddit batch interview failed: {e}")
        
        if results:
            self.send_response(command_id, "completed", result={
                "interviews_count": len(results),
                "results": results
            })
            print(f"  Batch interview done: {len(results)} agents")
            return True
        else:
            self.send_response(command_id, "failed", error="No successful interviews")
            return False
    
    def _get_interview_result(self, agent_id: int, platform: str) -> Dict[str, Any]:
        """Fetch the latest Interview result from the database."""
        db_path = os.path.join(self.simulation_dir, f"{platform}_simulation.db")
        
        result = {
            "agent_id": agent_id,
            "response": None,
            "timestamp": None
        }
        
        if not os.path.exists(db_path):
            return result
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Query the most recent Interview record
            cursor.execute("""
                SELECT user_id, info, created_at
                FROM trace
                WHERE action = ? AND user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (ActionType.INTERVIEW.value, agent_id))
            
            row = cursor.fetchone()
            if row:
                user_id, info_json, created_at = row
                try:
                    info = json.loads(info_json) if info_json else {}
                    result["response"] = info.get("response", info)
                    result["timestamp"] = created_at
                except json.JSONDecodeError:
                    result["response"] = info_json
            
            conn.close()
            
        except Exception as e:
            print(f"  Failed to read interview result: {e}")
        
        return result
    
    async def process_commands(self) -> bool:
        """
        Process all pending commands.

        Returns:
            True to keep running, False to exit.
        """
        command = self.poll_command()
        if not command:
            return True
        
        command_id = command.get("command_id")
        command_type = command.get("command_type")
        args = command.get("args", {})
        
        print(f"\nReceived IPC command: {command_type}, id={command_id}")
        
        if command_type == CommandType.INTERVIEW:
            await self.handle_interview(
                command_id,
                args.get("agent_id", 0),
                args.get("prompt", ""),
                args.get("platform")
            )
            return True
            
        elif command_type == CommandType.BATCH_INTERVIEW:
            await self.handle_batch_interview(
                command_id,
                args.get("interviews", []),
                args.get("platform")
            )
            return True
            
        elif command_type == CommandType.CLOSE_ENV:
            print("Received close-env command")
            self.send_response(command_id, "completed", result={"message": "Environment shutting down"})
            return False
        
        else:
            self.send_response(command_id, "failed", error=f"Unknown command type: {command_type}")
            return True


def load_config(config_path: str) -> Dict[str, Any]:
    """Load config file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# Action types to filter out (low analytical value)
FILTERED_ACTIONS = {'refresh', 'sign_up'}

# Action type mapping: database name -> canonical name
ACTION_TYPE_MAP = {
    'create_post': 'CREATE_POST',
    'like_post': 'LIKE_POST',
    'dislike_post': 'DISLIKE_POST',
    'repost': 'REPOST',
    'quote_post': 'QUOTE_POST',
    'follow': 'FOLLOW',
    'mute': 'MUTE',
    'create_comment': 'CREATE_COMMENT',
    'like_comment': 'LIKE_COMMENT',
    'dislike_comment': 'DISLIKE_COMMENT',
    'search_posts': 'SEARCH_POSTS',
    'search_user': 'SEARCH_USER',
    'trend': 'TREND',
    'do_nothing': 'DO_NOTHING',
    'interview': 'INTERVIEW',
}


def get_agent_names_from_config(config: Dict[str, Any]) -> Dict[int, str]:
    """
    Build a mapping of agent_id -> entity_name from simulation_config.

    This allows actions.jsonl to show real entity names instead of "Agent_0" codes.

    Args:
        config: Contents of simulation_config.json

    Returns:
        Dict mapping agent_id -> entity_name.
    """
    agent_names = {}
    agent_configs = config.get("agent_configs", [])
    
    for agent_config in agent_configs:
        agent_id = agent_config.get("agent_id")
        entity_name = agent_config.get("entity_name", f"Agent_{agent_id}")
        if agent_id is not None:
            agent_names[agent_id] = entity_name
    
    return agent_names


def fetch_new_actions_from_db(
    db_path: str,
    last_rowid: int,
    agent_names: Dict[int, str]
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Fetch new action records from the database and enrich them with context.

    Args:
        db_path: Path to the database file
        last_rowid: Max rowid processed last time (rowid avoids created_at format differences between Twitter/Reddit)
        agent_names: agent_id -> agent_name mapping

    Returns:
        (actions_list, new_last_rowid)
        - actions_list: list of dicts with agent_id, agent_name, action_type, action_args (with context)
        - new_last_rowid: new max rowid
    """
    actions = []
    new_last_rowid = last_rowid
    
    if not os.path.exists(db_path):
        return actions, new_last_rowid
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Use rowid to track processed records (rowid is SQLite's built-in auto-increment field)
        # This avoids created_at format differences (Twitter uses integer, Reddit uses datetime string)
        cursor.execute("""
            SELECT rowid, user_id, action, info
            FROM trace
            WHERE rowid > ?
            ORDER BY rowid ASC
        """, (last_rowid,))
        
        for rowid, user_id, action, info_json in cursor.fetchall():
            # Update max rowid
            new_last_rowid = rowid

            # Filter non-core actions
            if action in FILTERED_ACTIONS:
                continue

            # Parse action arguments
            try:
                action_args = json.loads(info_json) if info_json else {}
            except json.JSONDecodeError:
                action_args = {}
            
            # Simplify action_args, keeping only key fields (full content, no truncation)
            simplified_args = {}
            if 'content' in action_args:
                simplified_args['content'] = action_args['content']
            if 'post_id' in action_args:
                simplified_args['post_id'] = action_args['post_id']
            if 'comment_id' in action_args:
                simplified_args['comment_id'] = action_args['comment_id']
            if 'quoted_id' in action_args:
                simplified_args['quoted_id'] = action_args['quoted_id']
            if 'new_post_id' in action_args:
                simplified_args['new_post_id'] = action_args['new_post_id']
            if 'follow_id' in action_args:
                simplified_args['follow_id'] = action_args['follow_id']
            if 'query' in action_args:
                simplified_args['query'] = action_args['query']
            if 'like_id' in action_args:
                simplified_args['like_id'] = action_args['like_id']
            if 'dislike_id' in action_args:
                simplified_args['dislike_id'] = action_args['dislike_id']
            
            # Map action type name
            action_type = ACTION_TYPE_MAP.get(action, action.upper())

            # Enrich with context (post content, user names, etc.)
            _enrich_action_context(cursor, action_type, simplified_args, agent_names)
            
            actions.append({
                'agent_id': user_id,
                'agent_name': agent_names.get(user_id, f'Agent_{user_id}'),
                'action_type': action_type,
                'action_args': simplified_args,
            })
        
        conn.close()
    except Exception as e:
        print(f"Failed to read DB actions: {e}")
    
    return actions, new_last_rowid


def _enrich_action_context(
    cursor,
    action_type: str,
    action_args: Dict[str, Any],
    agent_names: Dict[int, str]
) -> None:
    """
    Enrich an action with context information (post content, user names, etc.).

    Args:
        cursor: Database cursor
        action_type: Action type string
        action_args: Action arguments dict (mutated in place)
        agent_names: agent_id -> agent_name mapping
    """
    try:
        # Like/dislike post: add post content and author
        if action_type in ('LIKE_POST', 'DISLIKE_POST'):
            post_id = action_args.get('post_id')
            if post_id:
                post_info = _get_post_info(cursor, post_id, agent_names)
                if post_info:
                    action_args['post_content'] = post_info.get('content', '')
                    action_args['post_author_name'] = post_info.get('author_name', '')
        
        # Repost: add original post content and author
        elif action_type == 'REPOST':
            new_post_id = action_args.get('new_post_id')
            if new_post_id:
                # Repost's original_post_id points to the original post
                cursor.execute("""
                    SELECT original_post_id FROM post WHERE post_id = ?
                """, (new_post_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    original_post_id = row[0]
                    original_info = _get_post_info(cursor, original_post_id, agent_names)
                    if original_info:
                        action_args['original_content'] = original_info.get('content', '')
                        action_args['original_author_name'] = original_info.get('author_name', '')
        
        # Quote post: add original post content, author, and quote comment
        elif action_type == 'QUOTE_POST':
            quoted_id = action_args.get('quoted_id')
            new_post_id = action_args.get('new_post_id')
            
            if quoted_id:
                original_info = _get_post_info(cursor, quoted_id, agent_names)
                if original_info:
                    action_args['original_content'] = original_info.get('content', '')
                    action_args['original_author_name'] = original_info.get('author_name', '')
            
            # Get the quote content from the quoting post
            if new_post_id:
                cursor.execute("""
                    SELECT quote_content FROM post WHERE post_id = ?
                """, (new_post_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    action_args['quote_content'] = row[0]
        
        # Follow user: add target user name
        elif action_type == 'FOLLOW':
            follow_id = action_args.get('follow_id')
            if follow_id:
                # Get followee_id from the follow table
                cursor.execute("""
                    SELECT followee_id FROM follow WHERE follow_id = ?
                """, (follow_id,))
                row = cursor.fetchone()
                if row:
                    followee_id = row[0]
                    target_name = _get_user_name(cursor, followee_id, agent_names)
                    if target_name:
                        action_args['target_user_name'] = target_name
        
        # Mute user: add target user name
        elif action_type == 'MUTE':
            # Get user_id or target_id from action_args
            target_id = action_args.get('user_id') or action_args.get('target_id')
            if target_id:
                target_name = _get_user_name(cursor, target_id, agent_names)
                if target_name:
                    action_args['target_user_name'] = target_name
        
        # Like/dislike comment: add comment content and author
        elif action_type in ('LIKE_COMMENT', 'DISLIKE_COMMENT'):
            comment_id = action_args.get('comment_id')
            if comment_id:
                comment_info = _get_comment_info(cursor, comment_id, agent_names)
                if comment_info:
                    action_args['comment_content'] = comment_info.get('content', '')
                    action_args['comment_author_name'] = comment_info.get('author_name', '')
        
        # Create comment: add parent post info
        elif action_type == 'CREATE_COMMENT':
            post_id = action_args.get('post_id')
            if post_id:
                post_info = _get_post_info(cursor, post_id, agent_names)
                if post_info:
                    action_args['post_content'] = post_info.get('content', '')
                    action_args['post_author_name'] = post_info.get('author_name', '')
    
    except Exception as e:
        # Context enrichment failure is non-fatal
        print(f"Failed to enrich action context: {e}")


def _get_post_info(
    cursor,
    post_id: int,
    agent_names: Dict[int, str]
) -> Optional[Dict[str, str]]:
    """
    Fetch post information.

    Args:
        cursor: Database cursor
        post_id: Post ID
        agent_names: agent_id -> agent_name mapping

    Returns:
        Dict with 'content' and 'author_name', or None.
    """
    try:
        cursor.execute("""
            SELECT p.content, p.user_id, u.agent_id
            FROM post p
            LEFT JOIN user u ON p.user_id = u.user_id
            WHERE p.post_id = ?
        """, (post_id,))
        row = cursor.fetchone()
        if row:
            content = row[0] or ''
            user_id = row[1]
            agent_id = row[2]
            
            # Prefer name from agent_names mapping
            author_name = ''
            if agent_id is not None and agent_id in agent_names:
                author_name = agent_names[agent_id]
            elif user_id:
                # Fall back to user table
                cursor.execute("SELECT name, user_name FROM user WHERE user_id = ?", (user_id,))
                user_row = cursor.fetchone()
                if user_row:
                    author_name = user_row[0] or user_row[1] or ''

            return {'content': content, 'author_name': author_name}
    except Exception:
        pass
    return None


def _get_user_name(
    cursor,
    user_id: int,
    agent_names: Dict[int, str]
) -> Optional[str]:
    """
    Get a user's display name.

    Args:
        cursor: Database cursor
        user_id: User ID
        agent_names: agent_id -> agent_name mapping

    Returns:
        User name string, or None.
    """
    try:
        cursor.execute("""
            SELECT agent_id, name, user_name FROM user WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if row:
            agent_id = row[0]
            name = row[1]
            user_name = row[2]
            
            # Prefer name from agent_names mapping
            if agent_id is not None and agent_id in agent_names:
                return agent_names[agent_id]
            return name or user_name or ''
    except Exception:
        pass
    return None


def _get_comment_info(
    cursor,
    comment_id: int,
    agent_names: Dict[int, str]
) -> Optional[Dict[str, str]]:
    """
    Fetch comment information.

    Args:
        cursor: Database cursor
        comment_id: Comment ID
        agent_names: agent_id -> agent_name mapping

    Returns:
        Dict with 'content' and 'author_name', or None.
    """
    try:
        cursor.execute("""
            SELECT c.content, c.user_id, u.agent_id
            FROM comment c
            LEFT JOIN user u ON c.user_id = u.user_id
            WHERE c.comment_id = ?
        """, (comment_id,))
        row = cursor.fetchone()
        if row:
            content = row[0] or ''
            user_id = row[1]
            agent_id = row[2]
            
            # Prefer name from agent_names mapping
            author_name = ''
            if agent_id is not None and agent_id in agent_names:
                author_name = agent_names[agent_id]
            elif user_id:
                # Fall back to user table
                cursor.execute("SELECT name, user_name FROM user WHERE user_id = ?", (user_id,))
                user_row = cursor.fetchone()
                if user_row:
                    author_name = user_row[0] or user_row[1] or ''

            return {'content': content, 'author_name': author_name}
    except Exception:
        pass
    return None


def _extract_azure_deployment(raw_url: str):
    """Extract deployment name and clean base_url from an Azure OpenAI full URL.

    Azure Portal gives URLs like:
      https://<resource>.cognitiveservices.azure.com/openai/deployments/<model>/chat/completions?api-version=...

    camel-ai needs the base_url WITHOUT /chat/completions and uses the model name
    passed as model_type to build the path — but Azure ignores the model field in
    the request body and routes by deployment name in the URL path.

    Strategy:
      1. If the URL contains /deployments/<name>/, extract <name> as the model.
      2. Strip /chat/completions (and /embeddings) suffix so camel-ai can append it.
      3. Preserve ?api-version as a separate string to inject via OPENAI_API_VERSION.
    """
    from urllib.parse import urlparse, parse_qs, urlunparse
    import re

    model = None
    api_version = None

    if not raw_url:
        return raw_url, model, api_version

    parsed = urlparse(raw_url)
    qs = parse_qs(parsed.query)
    if 'api-version' in qs:
        api_version = qs['api-version'][0]

    # Extract deployment name from path
    m = re.search(r'/deployments/([^/]+)', parsed.path)
    if m:
        model = m.group(1)

    # Strip /chat/completions and /embeddings from the path so camel-ai can append them
    clean_path = re.sub(r'/chat/completions.*$', '', parsed.path)
    clean_path = re.sub(r'/embeddings.*$', '', clean_path).rstrip('/')
    # Strip /openai/deployments/... so camel-ai doesn't duplicate it in the final URL
    clean_path = re.sub(r'/openai/deployments.*$', '', clean_path).rstrip('/')
    clean_url = urlunparse(parsed._replace(path=clean_path, query=''))

    return clean_url, model, api_version


def create_model(config: Dict[str, Any], use_boost: bool = False):
    """Create an LLM model for camel-ai.

    Supports dual-LLM setup (standard + boost) for parallel simulation.
    Detects Azure OpenAI URLs (cognitiveservices.azure.com or openai.azure.com)
    and uses ModelPlatformType.AZURE with the correct env vars; otherwise falls
    back to ModelPlatformType.OPENAI for standard OpenAI-compatible endpoints.

    LLM_CONTEXT_WINDOW sets the token budget for ScoreBasedContextCreator so
    camel-ai prunes agent memory before it exceeds the deployment's real limit.
    Default: 128000. Set lower (e.g. 32000) for deployments with tighter limits.
    """
    # Try to read from DB first (DB > env precedence)
    try:
        import sys as _sys
        import os as _os
        _scripts_dir = _os.path.dirname(_os.path.abspath(__file__))
        _backend_dir = _os.path.join(_scripts_dir, '..')
        if _backend_dir not in _sys.path:
            _sys.path.insert(0, _backend_dir)
        from app.config import Config as _Config
        from app.db import init_db as _init_db
        from app.config_db import get_config as _get_config
        _init_db(_Config.DATABASE_URL)
        _boost_api_key_bd = _get_config('llm.boost.api_key', '') or ''
        _boost_base_url_bd = _get_config('llm.boost.base_url', '') or ''
        _boost_model_bd = _get_config('llm.boost.model_name', '') or ''
        _std_api_key_bd = _get_config('llm.api_key', '') or ''
        _std_base_url_bd = _get_config('llm.base_url', '') or ''
        _std_model_bd = _get_config('llm.model_name', '') or ''
    except Exception:
        _boost_api_key_bd = ''
        _boost_base_url_bd = ''
        _boost_model_bd = ''
        _std_api_key_bd = ''
        _std_base_url_bd = ''
        _std_model_bd = ''

    boost_api_key = _boost_api_key_bd or os.environ.get("LLM_BOOST_API_KEY", "")
    boost_base_url = _boost_base_url_bd or os.environ.get("LLM_BOOST_BASE_URL", "")
    boost_model = _boost_model_bd or os.environ.get("LLM_BOOST_MODEL_NAME", "")
    has_boost_config = bool(boost_api_key)

    if use_boost and has_boost_config:
        llm_api_key = boost_api_key
        raw_url = boost_base_url
        llm_model_env = boost_model or os.environ.get("LLM_MODEL_NAME", "")
        config_label = "[Boost LLM]"
    else:
        llm_api_key = _std_api_key_bd or os.environ.get("LLM_API_KEY", "")
        raw_url = _std_base_url_bd or os.environ.get("LLM_BASE_URL", "")
        llm_model_env = _std_model_bd or os.environ.get("LLM_MODEL_NAME", "")
        config_label = "[Standard LLM]"

    # Parse Azure URL: extract deployment name, clean base_url, and api-version
    clean_url, deployment_from_url, api_version = _extract_azure_deployment(raw_url)

    # Deployment name from URL takes priority over env var
    llm_model = deployment_from_url or llm_model_env or config.get("llm_model", "gpt-4o-mini")

    if not llm_api_key:
        raise ValueError("Missing API key — set LLM_API_KEY in the project root .env file")

    is_azure = bool(deployment_from_url) or (
        raw_url and (
            "cognitiveservices.azure.com" in raw_url
            or "openai.azure.com" in raw_url
        )
    )

    # camel-ai uses model_config_dict["max_tokens"] as the context budget for
    # ScoreBasedContextCreator (token_limit pruning). It also passes the dict
    # directly to the OpenAI API, so any key present goes to the API call.
    # gpt-5.1 and newer o-series models reject "max_tokens" with a 400 error
    # and require "max_completion_tokens" instead.
    # Strategy: omit max_tokens from the config dict (camel-ai falls back to
    # model_type.token_limit, which for unknown model names is 999_999_999 —
    # fine for our use case since we don't rely on ScoreBasedContextCreator
    # pruning here). Use max_completion_tokens for the API call instead.
    context_window = int(os.environ.get("LLM_CONTEXT_WINDOW", "128000"))
    model_config = {"max_completion_tokens": context_window}

    if is_azure:
        # AzureOpenAIModel reads these specific env vars
        os.environ["AZURE_OPENAI_API_KEY"] = llm_api_key
        if clean_url:
            os.environ["AZURE_OPENAI_BASE_URL"] = clean_url
        if api_version:
            os.environ["AZURE_API_VERSION"] = api_version
        os.environ["AZURE_DEPLOYMENT_NAME"] = llm_model

        print(f"{config_label} [Azure] deployment={llm_model}, endpoint={clean_url[:60] if clean_url else 'default'}, context_window={context_window}...")

        return ModelFactory.create(
            model_platform=ModelPlatformType.AZURE,
            model_type=llm_model,
            model_config_dict=model_config,
            api_key=llm_api_key,
            url=clean_url or None,
            api_version=api_version,
            azure_deployment_name=llm_model,
        )
    else:
        os.environ["OPENAI_API_KEY"] = llm_api_key
        if clean_url:
            os.environ["OPENAI_API_BASE_URL"] = clean_url

        print(f"{config_label} [OpenAI] model={llm_model}, base_url={clean_url[:60] if clean_url else 'default'}, context_window={context_window}...")

        return ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=llm_model,
            model_config_dict=model_config,
            api_key=llm_api_key,
            url=clean_url or None,
        )


def get_active_agents_for_round(
    env,
    config: Dict[str, Any],
    current_hour: int,
    round_num: int
) -> List:
    """Determine which agents are active this round based on time and config."""
    time_config = config.get("time_config", {})
    agent_configs = config.get("agent_configs", [])
    
    base_min = time_config.get("agents_per_hour_min", 5)
    base_max = time_config.get("agents_per_hour_max", 20)
    
    peak_hours = time_config.get("peak_hours", [9, 10, 11, 14, 15, 20, 21, 22])
    off_peak_hours = time_config.get("off_peak_hours", [0, 1, 2, 3, 4, 5])
    
    if current_hour in peak_hours:
        multiplier = time_config.get("peak_activity_multiplier", 1.5)
    elif current_hour in off_peak_hours:
        multiplier = time_config.get("off_peak_activity_multiplier", 0.3)
    else:
        multiplier = 1.0
    
    target_count = int(random.uniform(base_min, base_max) * multiplier)
    
    candidates = []
    for cfg in agent_configs:
        agent_id = cfg.get("agent_id", 0)
        active_hours = cfg.get("active_hours", list(range(8, 23)))
        activity_level = cfg.get("activity_level", 0.5)
        
        if current_hour not in active_hours:
            continue
        
        if random.random() < activity_level:
            candidates.append(agent_id)
    
    selected_ids = random.sample(
        candidates, 
        min(target_count, len(candidates))
    ) if candidates else []
    
    active_agents = []
    for agent_id in selected_ids:
        try:
            agent = env.agent_graph.get_agent(agent_id)
            active_agents.append((agent_id, agent))
        except Exception:
            pass
    
    return active_agents


class PlatformSimulation:
    """Container for platform simulation results."""
    def __init__(self):
        self.env = None
        self.agent_graph = None
        self.total_actions = 0


async def run_twitter_simulation(
    config: Dict[str, Any], 
    simulation_dir: str,
    action_logger: Optional[PlatformActionLogger] = None,
    main_logger: Optional[SimulationLogManager] = None,
    max_rounds: Optional[int] = None
) -> PlatformSimulation:
    """Run Twitter simulation.

    Args:
        config: Simulation configuration
        simulation_dir: Simulation directory path
        action_logger: Platform action logger
        main_logger: Main log manager
        max_rounds: Max simulation rounds (optional, overrides config-derived count)

    Returns:
        PlatformSimulation with env and agent_graph.
    """
    result = PlatformSimulation()
    
    def log_info(msg):
        if main_logger:
            main_logger.info(f"[Twitter] {msg}")
        print(f"[Twitter] {msg}")
    
    log_info("Initializing...")
    _patch_social_agent_compaction("Twitter")

    # Twitter uses the standard LLM config
    model = create_model(config, use_boost=False)

    # OASIS Twitter uses CSV format
    profile_path = os.path.join(simulation_dir, "twitter_profiles.csv")
    if not os.path.exists(profile_path):
        log_info(f"Error: profile file not found: {profile_path}")
        return result
    
    result.agent_graph = await generate_twitter_agent_graph(
        profile_path=profile_path,
        model=model,
        available_actions=TWITTER_ACTIONS,
    )
    
    # Get real agent name mapping from config (entity_name instead of default Agent_X)
    agent_names = get_agent_names_from_config(config)
    # Fall back to OASIS default name if agent not in config
    for agent_id, agent in result.agent_graph.get_agents():
        if agent_id not in agent_names:
            agent_names[agent_id] = getattr(agent, 'name', f'Agent_{agent_id}')
        agent._platform_label = "Twitter"  # used by compaction logger

    db_path = os.path.join(simulation_dir, "twitter_simulation.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    # Use Azure OpenAI Embeddings for recsys instead of the local twhin-bert-base model
    # (~1.1 GB RAM) to avoid OOM kills on Azure Container Apps.
    # camel.OpenAIEmbedding reads OPENAI_API_KEY and OPENAI_API_BASE_URL, so we map
    # the LLM_EMBED_* variables (already in .env) to those names here.
    embed_api_key = os.environ.get("LLM_EMBED_API_KEY") or os.environ.get("LLM_API_KEY", "")
    embed_base_url = os.environ.get("LLM_EMBED_BASE_URL") or os.environ.get("LLM_BASE_URL", "")
    os.environ["OPENAI_API_KEY"] = embed_api_key
    os.environ["OPENAI_API_BASE_URL"] = embed_base_url

    _twitter_channel = OasisChannel()
    _twitter_platform = OasisPlatform(
        db_path=db_path,
        channel=_twitter_channel,
        recsys_type="twhin-bert",  # internal name; use_openai_embedding=True bypasses local model
        use_openai_embedding=True,
        refresh_rec_post_count=2,
        max_rec_post_len=2,
        following_post_count=3,
    )
    result.env = oasis.make(
        agent_graph=result.agent_graph,
        platform=_twitter_platform,
        database_path=db_path,
        semaphore=30,  # Limit max concurrent LLM requests to avoid API overload
    )

    await result.env.reset()
    log_info("Environment started")

    if action_logger:
        action_logger.log_simulation_start(config)

    total_actions = 0
    last_rowid = 0  # Track last processed rowid (avoids created_at format differences)

    # Run initial events
    event_config = config.get("event_config", {})
    initial_posts = event_config.get("initial_posts", [])

    # Log round 0 start (initial events phase)
    if action_logger:
        action_logger.log_round_start(0, 0)  # round 0, simulated_hour 0

    initial_action_count = 0
    if initial_posts:
        initial_actions = {}
        for post in initial_posts:
            agent_id = post.get("poster_agent_id", 0)
            content = post.get("content", "")
            try:
                agent = result.env.agent_graph.get_agent(agent_id)
                initial_actions[agent] = ManualAction(
                    action_type=ActionType.CREATE_POST,
                    action_args={"content": content}
                )

                if action_logger:
                    action_logger.log_action(
                        round_num=0,
                        agent_id=agent_id,
                        agent_name=agent_names.get(agent_id, f"Agent_{agent_id}"),
                        action_type="CREATE_POST",
                        action_args={"content": content}
                    )
                    total_actions += 1
                    initial_action_count += 1
            except Exception:
                pass

        if initial_actions:
            await result.env.step(initial_actions)
            log_info(f"Published {len(initial_actions)} initial posts")

    # Log round 0 end
    if action_logger:
        action_logger.log_round_end(0, initial_action_count)

    # Main simulation loop
    time_config = config.get("time_config", {})
    total_hours = time_config.get("total_simulation_hours", 72)
    minutes_per_round = time_config.get("minutes_per_round", 30)
    total_rounds = (total_hours * 60) // minutes_per_round

    if max_rounds is not None and max_rounds > 0 and max_rounds != total_rounds:
        log_info(f"Rounds override: config={total_rounds} -> max_rounds={max_rounds}")
        total_rounds = max_rounds

    start_time = datetime.now()
    completed_naturally = False

    for round_num in range(total_rounds):
        # Check for shutdown signal
        if _shutdown_event and _shutdown_event.is_set():
            if main_logger:
                main_logger.info(f"Shutdown signal received, stopping at round {round_num + 1}")
            break

        simulated_minutes = round_num * minutes_per_round
        simulated_hour = (simulated_minutes // 60) % 24
        simulated_day = simulated_minutes // (60 * 24) + 1

        active_agents = get_active_agents_for_round(
            result.env, config, simulated_hour, round_num
        )

        # Always log round start, even if no active agents
        if action_logger:
            action_logger.log_round_start(round_num + 1, simulated_hour)

        if not active_agents:
            # Also log round end with zero actions when no agents active
            if action_logger:
                action_logger.log_round_end(round_num + 1, 0)
            continue

        actions = {agent: LLMAction() for _, agent in active_agents}
        await result.env.step(actions)

        # Fetch actual executed actions from DB and log them
        actual_actions, last_rowid = fetch_new_actions_from_db(
            db_path, last_rowid, agent_names
        )

        round_action_count = 0
        for action_data in actual_actions:
            if action_logger:
                action_logger.log_action(
                    round_num=round_num + 1,
                    agent_id=action_data['agent_id'],
                    agent_name=action_data['agent_name'],
                    action_type=action_data['action_type'],
                    action_args=action_data['action_args']
                )
                total_actions += 1
                round_action_count += 1

        if action_logger:
            action_logger.log_round_end(round_num + 1, round_action_count)

        if (round_num + 1) % 20 == 0:
            progress = (round_num + 1) / total_rounds * 100
            log_info(f"Day {simulated_day}, {simulated_hour:02d}:00 - Round {round_num + 1}/{total_rounds} ({progress:.1f}%)")

        if round_num + 1 == total_rounds:
            completed_naturally = True

    # Note: do NOT close the environment; it is kept alive for Interview commands

    # Only write simulation_end when all rounds finished — not when interrupted by signal
    if action_logger:
        if completed_naturally:
            action_logger.log_simulation_end(total_rounds, total_actions)
        else:
            action_logger.log_simulation_stopped(round_num + 1 if total_rounds > 0 else 0, total_actions)

    result.total_actions = total_actions
    elapsed = (datetime.now() - start_time).total_seconds()
    log_info(f"Simulation loop done! Elapsed: {elapsed:.1f}s, total actions: {total_actions}, completed={completed_naturally}")

    return result


async def run_reddit_simulation(

    config: Dict[str, Any], 
    simulation_dir: str,
    action_logger: Optional[PlatformActionLogger] = None,
    main_logger: Optional[SimulationLogManager] = None,
    max_rounds: Optional[int] = None
) -> PlatformSimulation:
    """Run Reddit simulation.

    Args:
        config: Simulation configuration
        simulation_dir: Simulation directory path
        action_logger: Platform action logger
        main_logger: Main log manager
        max_rounds: Max simulation rounds (optional, overrides config-derived count)

    Returns:
        PlatformSimulation with env and agent_graph.
    """
    result = PlatformSimulation()
    
    def log_info(msg):
        if main_logger:
            main_logger.info(f"[Reddit] {msg}")
        print(f"[Reddit] {msg}")
    
    log_info("Initializing...")
    _patch_social_agent_compaction("Reddit")

    # Reddit uses the boost LLM config if available, otherwise falls back to standard
    model = create_model(config, use_boost=True)
    
    profile_path = os.path.join(simulation_dir, "reddit_profiles.json")
    if not os.path.exists(profile_path):
        log_info(f"Error: profile file not found: {profile_path}")
        return result
    
    result.agent_graph = await generate_reddit_agent_graph(
        profile_path=profile_path,
        model=model,
        available_actions=REDDIT_ACTIONS,
    )
    
    # Get real agent name mapping from config
    agent_names = get_agent_names_from_config(config)
    # Fall back to OASIS default name if agent not in config
    for agent_id, agent in result.agent_graph.get_agents():
        if agent_id not in agent_names:
            agent_names[agent_id] = getattr(agent, 'name', f'Agent_{agent_id}')
        agent._platform_label = "Reddit"  # used by compaction logger

    db_path = os.path.join(simulation_dir, "reddit_simulation.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    
    result.env = oasis.make(
        agent_graph=result.agent_graph,
        platform=oasis.DefaultPlatformType.REDDIT,
        database_path=db_path,
        semaphore=30,  # Limit max concurrent LLM requests to avoid API overload
    )

    await result.env.reset()
    log_info("Environment started")

    if action_logger:
        action_logger.log_simulation_start(config)

    total_actions = 0
    last_rowid = 0  # Track last processed rowid (avoids created_at format differences)

    # Run initial events
    event_config = config.get("event_config", {})
    initial_posts = event_config.get("initial_posts", [])

    # Log round 0 start (initial events phase)
    if action_logger:
        action_logger.log_round_start(0, 0)  # round 0, simulated_hour 0

    initial_action_count = 0
    if initial_posts:
        initial_actions = {}
        for post in initial_posts:
            agent_id = post.get("poster_agent_id", 0)
            content = post.get("content", "")
            try:
                agent = result.env.agent_graph.get_agent(agent_id)
                if agent in initial_actions:
                    if not isinstance(initial_actions[agent], list):
                        initial_actions[agent] = [initial_actions[agent]]
                    initial_actions[agent].append(ManualAction(
                        action_type=ActionType.CREATE_POST,
                        action_args={"content": content}
                    ))
                else:
                    initial_actions[agent] = ManualAction(
                        action_type=ActionType.CREATE_POST,
                        action_args={"content": content}
                    )
                
                if action_logger:
                    action_logger.log_action(
                        round_num=0,
                        agent_id=agent_id,
                        agent_name=agent_names.get(agent_id, f"Agent_{agent_id}"),
                        action_type="CREATE_POST",
                        action_args={"content": content}
                    )
                    total_actions += 1
                    initial_action_count += 1
            except Exception:
                pass
        
        if initial_actions:
            await result.env.step(initial_actions)
            log_info(f"Published {len(initial_actions)} initial posts")
    
    # Log round 0 end
    if action_logger:
        action_logger.log_round_end(0, initial_action_count)

    # Main simulation loop
    time_config = config.get("time_config", {})
    total_hours = time_config.get("total_simulation_hours", 72)
    minutes_per_round = time_config.get("minutes_per_round", 30)
    total_rounds = (total_hours * 60) // minutes_per_round
    
    if max_rounds is not None and max_rounds > 0 and max_rounds != total_rounds:
        log_info(f"Rounds override: config={total_rounds} -> max_rounds={max_rounds}")
        total_rounds = max_rounds

    start_time = datetime.now()
    completed_naturally = False

    for round_num in range(total_rounds):
        # Check for shutdown signal
        if _shutdown_event and _shutdown_event.is_set():
            if main_logger:
                main_logger.info(f"Shutdown signal received, stopping at round {round_num + 1}")
            break

        simulated_minutes = round_num * minutes_per_round
        simulated_hour = (simulated_minutes // 60) % 24
        simulated_day = simulated_minutes // (60 * 24) + 1

        active_agents = get_active_agents_for_round(
            result.env, config, simulated_hour, round_num
        )

        # Always log round start, even if no active agents
        if action_logger:
            action_logger.log_round_start(round_num + 1, simulated_hour)

        if not active_agents:
            # Also log round end with zero actions when no agents active
            if action_logger:
                action_logger.log_round_end(round_num + 1, 0)
            continue

        actions = {agent: LLMAction() for _, agent in active_agents}
        await result.env.step(actions)

        # Fetch actual executed actions from DB and log them
        actual_actions, last_rowid = fetch_new_actions_from_db(
            db_path, last_rowid, agent_names
        )

        round_action_count = 0
        for action_data in actual_actions:
            if action_logger:
                action_logger.log_action(
                    round_num=round_num + 1,
                    agent_id=action_data['agent_id'],
                    agent_name=action_data['agent_name'],
                    action_type=action_data['action_type'],
                    action_args=action_data['action_args']
                )
                total_actions += 1
                round_action_count += 1

        if action_logger:
            action_logger.log_round_end(round_num + 1, round_action_count)

        if (round_num + 1) % 20 == 0:
            progress = (round_num + 1) / total_rounds * 100
            log_info(f"Day {simulated_day}, {simulated_hour:02d}:00 - Round {round_num + 1}/{total_rounds} ({progress:.1f}%)")

        if round_num + 1 == total_rounds:
            completed_naturally = True

    # Note: do NOT close the environment; it is kept alive for Interview commands

    # Only write simulation_end when all rounds finished — not when interrupted by signal
    if action_logger:
        if completed_naturally:
            action_logger.log_simulation_end(total_rounds, total_actions)
        else:
            action_logger.log_simulation_stopped(round_num + 1 if total_rounds > 0 else 0, total_actions)

    result.total_actions = total_actions
    elapsed = (datetime.now() - start_time).total_seconds()
    log_info(f"Simulation loop done! Elapsed: {elapsed:.1f}s, total actions: {total_actions}")

    return result


async def main():
    parser = argparse.ArgumentParser(description='OASIS dual-platform parallel simulation')
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to config file (simulation_config.json)'
    )
    parser.add_argument(
        '--twitter-only',
        action='store_true',
        help='Run Twitter simulation only'
    )
    parser.add_argument(
        '--reddit-only',
        action='store_true',
        help='Run Reddit simulation only'
    )
    parser.add_argument(
        '--max-rounds',
        type=int,
        default=None,
        help='Max simulation rounds (optional; overrides config-derived round count)'
    )
    parser.add_argument(
        '--no-wait',
        action='store_true',
        default=False,
        help='Close environment immediately after simulation completes without entering wait-for-commands mode'
    )
    
    args = parser.parse_args()
    
    # Create shutdown event at startup so the whole program can respond to signals
    global _shutdown_event
    _shutdown_event = asyncio.Event()
    
    if not os.path.exists(args.config):
        print(f"Error: config file not found: {args.config}")
        sys.exit(1)
    
    config = load_config(args.config)
    simulation_dir = os.path.dirname(args.config) or "."
    wait_for_commands = not args.no_wait
    
    # Initialize logging (disable OASIS logging, clean up old files)
    init_logging_for_simulation(simulation_dir)

    # Create log managers
    log_manager = SimulationLogManager(simulation_dir)
    twitter_logger = log_manager.get_twitter_logger()
    reddit_logger = log_manager.get_reddit_logger()
    
    log_manager.info("=" * 60)
    log_manager.info("OASIS Dual-Platform Parallel Simulation")
    log_manager.info(f"Config file: {args.config}")
    log_manager.info(f"Simulation ID: {config.get('simulation_id', 'unknown')}")
    log_manager.info(f"Wait-for-commands mode: {'enabled' if wait_for_commands else 'disabled'}")
    log_manager.info("=" * 60)

    time_config = config.get("time_config", {})
    total_hours = time_config.get('total_simulation_hours', 72)
    minutes_per_round = time_config.get('minutes_per_round', 30)
    config_total_rounds = (total_hours * 60) // minutes_per_round

    log_manager.info("Simulation parameters:")
    log_manager.info(f"  - Total simulation time: {total_hours} hours")
    log_manager.info(f"  - Time per round: {minutes_per_round} minutes")
    log_manager.info(f"  - Config total rounds: {config_total_rounds}")
    if args.max_rounds:
        log_manager.info(f"  - Max rounds override: {args.max_rounds}")
    log_manager.info(f"  - Agent count: {len(config.get('agent_configs', []))}")

    log_manager.info("Log structure:")
    log_manager.info(f"  - Main log: simulation.log")
    log_manager.info(f"  - Twitter actions: twitter/actions.jsonl")
    log_manager.info(f"  - Reddit actions: reddit/actions.jsonl")
    log_manager.info("=" * 60)
    
    start_time = datetime.now()
    
    # Store results from both platforms
    twitter_result: Optional[PlatformSimulation] = None
    reddit_result: Optional[PlatformSimulation] = None
    
    if args.twitter_only:
        twitter_result = await run_twitter_simulation(config, simulation_dir, twitter_logger, log_manager, args.max_rounds)
    elif args.reddit_only:
        reddit_result = await run_reddit_simulation(config, simulation_dir, reddit_logger, log_manager, args.max_rounds)
    else:
        # Run both platforms in parallel (each with its own logger)
        results = await asyncio.gather(
            run_twitter_simulation(config, simulation_dir, twitter_logger, log_manager, args.max_rounds),
            run_reddit_simulation(config, simulation_dir, reddit_logger, log_manager, args.max_rounds),
        )
        twitter_result, reddit_result = results
    
    total_elapsed = (datetime.now() - start_time).total_seconds()
    log_manager.info("=" * 60)
    log_manager.info(f"Simulation loop complete! Total elapsed: {total_elapsed:.1f}s")

    # Enter wait-for-commands mode if requested
    if wait_for_commands:
        log_manager.info("")
        log_manager.info("=" * 60)
        log_manager.info("Entering wait-for-commands mode — environment remains active")
        log_manager.info("Supported commands: interview, batch_interview, close_env")
        log_manager.info("=" * 60)
        
        # Create IPC handler
        ipc_handler = ParallelIPCHandler(
            simulation_dir=simulation_dir,
            twitter_env=twitter_result.env if twitter_result else None,
            twitter_agent_graph=twitter_result.agent_graph if twitter_result else None,
            reddit_env=reddit_result.env if reddit_result else None,
            reddit_agent_graph=reddit_result.agent_graph if reddit_result else None
        )
        ipc_handler.update_status("alive")
        
        # Wait-for-commands loop (uses global _shutdown_event)
        try:
            while not _shutdown_event.is_set():
                should_continue = await ipc_handler.process_commands()
                if not should_continue:
                    break
                # Use wait_for instead of sleep so we can respond to shutdown_event
                try:
                    await asyncio.wait_for(_shutdown_event.wait(), timeout=0.5)
                    break  # Shutdown signal received
                except asyncio.TimeoutError:
                    pass  # Timeout: continue loop
        except KeyboardInterrupt:
            print("\nInterrupt signal received")
        except asyncio.CancelledError:
            print("\nTask cancelled")
        except Exception as e:
            print(f"\nCommand processing error: {e}")
        
        log_manager.info("\nShutting down environments...")
        ipc_handler.update_status("stopped")

    # Close environments
    if twitter_result and twitter_result.env:
        await twitter_result.env.close()
        log_manager.info("[Twitter] Environment closed")

    if reddit_result and reddit_result.env:
        await reddit_result.env.close()
        log_manager.info("[Reddit] Environment closed")

    log_manager.info("=" * 60)
    log_manager.info("All done!")
    log_manager.info("Log files:")
    log_manager.info(f"  - {os.path.join(simulation_dir, 'simulation.log')}")
    log_manager.info(f"  - {os.path.join(simulation_dir, 'twitter', 'actions.jsonl')}")
    log_manager.info(f"  - {os.path.join(simulation_dir, 'reddit', 'actions.jsonl')}")
    log_manager.info("=" * 60)


def setup_signal_handlers(loop=None):
    """
    Set up signal handlers to ensure clean exit on SIGTERM/SIGINT.

    In persistent simulation mode, the process stays alive after simulation
    completes to handle interview commands. On termination signal:
    1. Notify the asyncio loop to exit the wait loop
    2. Let the program clean up resources (close DB, environments, etc.)
    3. Then exit
    """
    def signal_handler(signum, frame):
        global _cleanup_done
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        print(f"\nReceived {sig_name} signal, shutting down...")
        
        if not _cleanup_done:
            _cleanup_done = True
            # Signal the asyncio loop to exit (allowing resource cleanup)
            if _shutdown_event:
                _shutdown_event.set()

        # Do NOT call sys.exit() immediately — let the asyncio loop exit cleanly
        # If we receive the signal a second time, force exit
        else:
            print("Force exit...")
            sys.exit(1)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


if __name__ == "__main__":
    setup_signal_handlers()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted")
    except SystemExit:
        pass
    finally:
        # Clean up multiprocessing resource tracker (prevents exit warnings)
        try:
            from multiprocessing import resource_tracker
            resource_tracker._resource_tracker._stop()
        except Exception:
            pass
        print("Simulation process exited")
