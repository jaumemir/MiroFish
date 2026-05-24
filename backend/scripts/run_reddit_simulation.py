"""
OASIS Reddit simulation preset script.
Reads parameters from the simulation config file and runs the simulation fully automated.

Features:
- After simulation completes, stays alive waiting for IPC commands
- Supports Interview commands (single agent and batch) via IPC
- Supports remote close_env command

Usage:
    python run_reddit_simulation.py --config /path/to/simulation_config.json
    python run_reddit_simulation.py --config /path/to/simulation_config.json --no-wait
"""

import argparse
import asyncio
import json
import logging
import os
import random
import signal
import sys
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

# Global variables for signal handling
_shutdown_event = None
_cleanup_done = False

# Add project paths
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_scripts_dir, '..'))
_project_root = os.path.abspath(os.path.join(_backend_dir, '..'))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, _backend_dir)

# Load .env from project root (contains LLM_API_KEY etc.)
from dotenv import load_dotenv
_env_file = os.path.join(_project_root, '.env')
if os.path.exists(_env_file):
    load_dotenv(_env_file)
else:
    _backend_env = os.path.join(_backend_dir, '.env')
    if os.path.exists(_backend_env):
        load_dotenv(_backend_env)


import re


class UnicodeFormatter(logging.Formatter):
    """Custom formatter that converts Unicode escape sequences to readable characters."""
    
    UNICODE_ESCAPE_PATTERN = re.compile(r'\\u([0-9a-fA-F]{4})')
    
    def format(self, record):
        result = super().format(record)
        
        def replace_unicode(match):
            try:
                return chr(int(match.group(1), 16))
            except (ValueError, OverflowError):
                return match.group(0)
        
        return self.UNICODE_ESCAPE_PATTERN.sub(replace_unicode, result)


class MaxTokensWarningFilter(logging.Filter):
    """Filter out camel-ai warnings about max_tokens (we intentionally omit it)."""

    def filter(self, record):
        if "max_tokens" in record.getMessage() and "Invalid or missing" in record.getMessage():
            return False
        return True


# Add filter at module load time, before any camel code runs
logging.getLogger().addFilter(MaxTokensWarningFilter())


def setup_oasis_logging(log_dir: str):
    """Configure OASIS logging to fixed-name log files."""
    os.makedirs(log_dir, exist_ok=True)

    # Remove old log files
    for f in os.listdir(log_dir):
        old_log = os.path.join(log_dir, f)
        if os.path.isfile(old_log) and f.endswith('.log'):
            try:
                os.remove(old_log)
            except OSError:
                pass
    
    formatter = UnicodeFormatter("%(levelname)s - %(asctime)s - %(name)s - %(message)s")
    
    loggers_config = {
        "social.agent": os.path.join(log_dir, "social.agent.log"),
        "social.twitter": os.path.join(log_dir, "social.twitter.log"),
        "social.rec": os.path.join(log_dir, "social.rec.log"),
        "oasis.env": os.path.join(log_dir, "oasis.env.log"),
        "table": os.path.join(log_dir, "table.log"),
    }
    
    for logger_name, log_file in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.propagate = False


try:
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType
    import oasis
    from oasis import (
        ActionType,
        LLMAction,
        ManualAction,
        generate_reddit_agent_graph
    )
    from run_parallel_simulation import create_model as _parallel_create_model
except ImportError as e:
    print(f"Error: missing dependency {e}")
    print("Install with: pip install oasis-ai camel-ai")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Context-compaction: Reddit agents accumulate long conversation histories that
# exceed the model's context window. Before every LLM call, count tokens; if
# they exceed COMPACTION_THRESHOLD, summarise the history with LLM_SMALL and
# replace it with a single compact record.
# ─────────────────────────────────────────────────────────────────────────────
COMPACTION_THRESHOLD = int(os.environ.get("AGENT_COMPACTION_THRESHOLD", "150000"))
COMPACTION_TARGET    = int(os.environ.get("AGENT_COMPACTION_TARGET",    "40000"))


def _create_small_client():
    from openai import OpenAI as _OpenAI
    api_key  = os.environ.get("LLM_SMALL_API_KEY")  or os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_SMALL_BASE_URL")  or os.environ.get("LLM_BASE_URL", "")
    model    = os.environ.get("LLM_SMALL_MODEL_NAME") or os.environ.get("LLM_MODEL_NAME", "gpt-4o-mini")
    return _OpenAI(api_key=api_key, base_url=base_url), model


_small_client = None
_small_model  = None


def _get_small_client():
    global _small_client, _small_model
    if _small_client is None:
        _small_client, _small_model = _create_small_client()
    return _small_client, _small_model


def _count_memory_tokens(agent) -> int:
    try:
        messages, num_tokens = agent.memory.get_context()
        return num_tokens
    except Exception:
        return 0


def _compact_agent_memory(agent) -> bool:
    try:
        from camel.messages import BaseMessage
        from camel.types import OpenAIBackendRole
        from camel.memories.records import MemoryRecord

        storage = agent.memory._chat_history_block.storage
        all_records = storage.load()

        if len(all_records) < 4:
            return False

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

        history_text = ""
        for r in history_records:
            msg = r.get("message", {})
            role    = r.get("role_at_backend", "user")
            content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
            history_text += f"[{role}]: {content}\n\n"
        history_text = history_text[-200_000:]

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

        new_records = system_records + [summary_record.to_dict()]
        storage.memory_list.clear()
        storage.memory_list.extend(new_records)

        agent_id = getattr(agent, 'social_agent_id', '?')
        print(f"  [Reddit] Agent {agent_id}: memory compacted "
              f"({len(history_records)} turns → 1 summary)", flush=True)
        return True

    except Exception as e:
        agent_id = getattr(agent, 'social_agent_id', '?')
        print(f"  [Reddit] Agent {agent_id}: compaction failed: {e}", flush=True)
        return False


_compaction_patch_applied = False


def _patch_social_agent_compaction():
    global _compaction_patch_applied
    if _compaction_patch_applied:
        return
    _compaction_patch_applied = True

    from oasis.social_agent.agent import SocialAgent

    _original_perform = SocialAgent.perform_action_by_llm

    async def _perform_with_compaction(self):
        tokens = _count_memory_tokens(self)
        if tokens > COMPACTION_THRESHOLD:
            _compact_agent_memory(self)
        return await _original_perform(self)

    SocialAgent.perform_action_by_llm = _perform_with_compaction


# IPC constants
IPC_COMMANDS_DIR = "ipc_commands"
IPC_RESPONSES_DIR = "ipc_responses"
ENV_STATUS_FILE = "env_status.json"

class CommandType:
    """IPC command type constants."""
    INTERVIEW = "interview"
    BATCH_INTERVIEW = "batch_interview"
    CLOSE_ENV = "close_env"


class IPCHandler:
    """IPC command handler."""

    def __init__(self, simulation_dir: str, env, agent_graph):
        self.simulation_dir = simulation_dir
        self.env = env
        self.agent_graph = agent_graph
        self.commands_dir = os.path.join(simulation_dir, IPC_COMMANDS_DIR)
        self.responses_dir = os.path.join(simulation_dir, IPC_RESPONSES_DIR)
        self.status_file = os.path.join(simulation_dir, ENV_STATUS_FILE)
        self._running = True

        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)

    def update_status(self, status: str):
        """Update environment status."""
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump({
                "status": status,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def poll_command(self) -> Optional[Dict[str, Any]]:
        """Poll for pending commands."""
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
        """Send IPC response."""
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
        
        # Remove command file after responding
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass
    
    async def handle_interview(self, command_id: str, agent_id: int, prompt: str) -> bool:
        """Handle a single-agent interview command. Returns True on success."""
        try:
            agent = self.agent_graph.get_agent(agent_id)
            interview_action = ManualAction(
                action_type=ActionType.INTERVIEW,
                action_args={"prompt": prompt}
            )
            actions = {agent: interview_action}
            await self.env.step(actions)
            result = self._get_interview_result(agent_id)
            self.send_response(command_id, "completed", result=result)
            print(f"  Interview done: agent_id={agent_id}")
            return True
        except Exception as e:
            error_msg = str(e)
            print(f"  Interview failed: agent_id={agent_id}, error={error_msg}")
            self.send_response(command_id, "failed", error=error_msg)
            return False

    async def handle_batch_interview(self, command_id: str, interviews: List[Dict]) -> bool:
        """Handle a batch-interview command. interviews: [{"agent_id": int, "prompt": str}, ...]"""
        try:
            actions = {}
            agent_prompts = {}
            for interview in interviews:
                agent_id = interview.get("agent_id") or 0
                prompt = interview.get("prompt", "")
                try:
                    agent = self.agent_graph.get_agent(agent_id)
                    actions[agent] = ManualAction(
                        action_type=ActionType.INTERVIEW,
                        action_args={"prompt": prompt}
                    )
                    agent_prompts[agent_id] = prompt
                except Exception as e:
                    print(f"  Warning: could not get agent {agent_id}: {e}")
            if not actions:
                self.send_response(command_id, "failed", error="No valid agents")
                return False
            await self.env.step(actions)
            results = {}
            for agent_id in agent_prompts.keys():
                results[agent_id] = self._get_interview_result(agent_id)
            self.send_response(command_id, "completed", result={
                "interviews_count": len(results),
                "results": results
            })
            print(f"  Batch interview done: {len(results)} agents")
            return True
        except Exception as e:
            error_msg = str(e)
            print(f"  Batch interview failed: {error_msg}")
            self.send_response(command_id, "failed", error=error_msg)
            return False

    def _get_interview_result(self, agent_id: int) -> Dict[str, Any]:
        """Fetch the latest interview result for agent_id from the DB."""
        db_path = os.path.join(self.simulation_dir, "reddit_simulation.db")

        result = {
            "agent_id": agent_id,
            "response": None,
            "timestamp": None
        }

        if not os.path.exists(db_path):
            return result

        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Query latest interview record
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

        except Exception as e:
            print(f"  Failed to read interview result: {e}")
        finally:
            if conn:
                conn.close()

        return result
    
    async def process_commands(self) -> bool:
        """Process all pending IPC commands. Returns False when env should exit."""
        command = self.poll_command()
        if not command:
            return True
        
        command_id = command.get("command_id")
        command_type = command.get("command_type")
        args = command.get("args", {})
        
        print(f"\nIPC command received: {command_type}, id={command_id}")
        
        if command_type == CommandType.INTERVIEW:
            await self.handle_interview(
                command_id,
                args.get("agent_id", 0),
                args.get("prompt", "")
            )
            return True
            
        elif command_type == CommandType.BATCH_INTERVIEW:
            await self.handle_batch_interview(
                command_id,
                args.get("interviews", [])
            )
            return True
            
        elif command_type == CommandType.CLOSE_ENV:
            print("Received close_env command")
            self.send_response(command_id, "completed", result={"message": "Environment closing"})
            return False
        else:
            self.send_response(command_id, "failed", error=f"Unknown command type: {command_type}")
            return True


class RedditSimulationRunner:
    """Reddit simulation runner."""

    # Available Reddit actions (INTERVIEW is triggered only via ManualAction)
    AVAILABLE_ACTIONS = [
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
    
    def __init__(self, config_path: str, wait_for_commands: bool = True):
        self.config_path = config_path
        self.config = self._load_config()
        self.simulation_dir = os.path.dirname(config_path)
        self.wait_for_commands = wait_for_commands
        self.env = None
        self.agent_graph = None
        self.ipc_handler = None
        
    def _load_config(self) -> Dict[str, Any]:
        """Load simulation config from JSON."""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _get_profile_path(self) -> str:
        """Return path to the Reddit profiles JSON file."""
        return os.path.join(self.simulation_dir, "reddit_profiles.json")
    
    def _get_db_path(self) -> str:
        """Return path to the SQLite simulation database."""
        return os.path.join(self.simulation_dir, "reddit_simulation.db")
    
    def _create_model(self):
        """Create LLM model using the same Azure-aware logic as run_parallel_simulation."""
        return _parallel_create_model(self.config)
    
    def _get_active_agents_for_round(
        self,
        env,
        current_hour: int,
        round_num: int
    ) -> List:
        """Determine which agents are active for this round based on time and config."""
        time_config = self.config.get("time_config", {})
        agent_configs = self.config.get("agent_configs", [])
        
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
    
    async def run(self, max_rounds: int = None):
        """Run the Reddit simulation.

        max_rounds: if provided, overrides the round count calculated from
        time_config. A value larger than the calculated count extends the
        simulation; a smaller value truncates it.
        """
        print("=" * 60)
        print("OASIS Reddit Simulation")
        print(f"Config: {self.config_path}")
        print(f"Simulation ID: {self.config.get('simulation_id', 'unknown')}")
        print(f"Wait-for-commands mode: {'enabled' if self.wait_for_commands else 'disabled'}")
        print("=" * 60)

        time_config = self.config.get("time_config", {})
        total_hours = time_config.get("total_simulation_hours", 72)
        minutes_per_round = time_config.get("minutes_per_round", 30)
        total_rounds = (total_hours * 60) // minutes_per_round

        # If max_rounds is specified it acts as an override: use it directly
        # (truncating or extending relative to the config-derived count).
        if max_rounds is not None and max_rounds > 0 and max_rounds != total_rounds:
            print(f"\nRounds override: config={total_rounds} -> max_rounds={max_rounds}")
            total_rounds = max_rounds

        print(f"\nSimulation parameters:")
        print(f"  - Total simulated hours: {total_hours}h")
        print(f"  - Minutes per round: {minutes_per_round}")
        print(f"  - Total rounds: {total_rounds}")
        if max_rounds:
            print(f"  - Max rounds override: {max_rounds}")
        print(f"  - Agents: {len(self.config.get('agent_configs', []))}")

        print("\nInitializing LLM model...")
        model = self._create_model()

        print("Loading agent profiles...")
        profile_path = self._get_profile_path()
        if not os.path.exists(profile_path):
            print(f"Error: profile file not found: {profile_path}")
            return

        self.agent_graph = await generate_reddit_agent_graph(
            profile_path=profile_path,
            model=model,
            available_actions=self.AVAILABLE_ACTIONS,
        )

        _patch_social_agent_compaction()

        db_path = self._get_db_path()
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"Removed old database: {db_path}")

        print("Creating OASIS environment...")
        self.env = oasis.make(
            agent_graph=self.agent_graph,
            platform=oasis.DefaultPlatformType.REDDIT,
            database_path=db_path,
            semaphore=30,  # cap concurrent LLM requests to avoid API overload
        )

        await self.env.reset()
        print("Environment ready\n")

        self.ipc_handler = IPCHandler(self.simulation_dir, self.env, self.agent_graph)
        self.ipc_handler.update_status("running")

        event_config = self.config.get("event_config", {})
        initial_posts = event_config.get("initial_posts", [])

        if initial_posts:
            print(f"Publishing initial posts ({len(initial_posts)})...")
            initial_actions = {}
            for post in initial_posts:
                agent_id = post.get("poster_agent_id", 0)
                content = post.get("content", "")
                try:
                    agent = self.env.agent_graph.get_agent(agent_id)
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
                except Exception as e:
                    print(f"  Warning: could not create initial post for agent {agent_id}: {e}")

            if initial_actions:
                await self.env.step(initial_actions)
                print(f"  Published {len(initial_actions)} initial posts")

        print("\nStarting simulation loop...")
        start_time = datetime.now()

        for round_num in range(total_rounds):
            simulated_minutes = round_num * minutes_per_round
            simulated_hour = (simulated_minutes // 60) % 24
            simulated_day = simulated_minutes // (60 * 24) + 1

            active_agents = self._get_active_agents_for_round(
                self.env, simulated_hour, round_num
            )

            if not active_agents:
                continue

            actions = {
                agent: LLMAction()
                for _, agent in active_agents
            }

            await self.env.step(actions)

            if (round_num + 1) % 10 == 0 or round_num == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                progress = (round_num + 1) / total_rounds * 100
                print(f"  [Day {simulated_day}, {simulated_hour:02d}:00] "
                      f"Round {round_num + 1}/{total_rounds} ({progress:.1f}%) "
                      f"- {len(active_agents)} agents active "
                      f"- elapsed: {elapsed:.1f}s")

        total_elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\nSimulation loop complete!")
        print(f"  - Total time: {total_elapsed:.1f}s")
        print(f"  - Database: {db_path}")

        if self.wait_for_commands:
            print("\n" + "=" * 60)
            print("Entering wait-for-commands mode — environment stays alive")
            print("Supported commands: interview, batch_interview, close_env")
            print("=" * 60)

            self.ipc_handler.update_status("alive")

            try:
                while not _shutdown_event.is_set():
                    should_continue = await self.ipc_handler.process_commands()
                    if not should_continue:
                        break
                    try:
                        await asyncio.wait_for(_shutdown_event.wait(), timeout=0.5)
                        break
                    except asyncio.TimeoutError:
                        pass
            except KeyboardInterrupt:
                print("\nInterrupt received")
            except asyncio.CancelledError:
                print("\nTask cancelled")
            except Exception as e:
                print(f"\nCommand processing error: {e}")

            print("\nShutting down environment...")

        self.ipc_handler.update_status("stopped")
        await self.env.close()

        print("Environment closed")
        print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description='OASIS Reddit simulation')
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to simulation_config.json'
    )
    parser.add_argument(
        '--max-rounds',
        type=int,
        default=None,
        help='Override total rounds (can extend or truncate config-derived count)'
    )
    parser.add_argument(
        '--no-wait',
        action='store_true',
        default=False,
        help='Close environment immediately after simulation instead of waiting for commands'
    )

    args = parser.parse_args()

    global _shutdown_event
    _shutdown_event = asyncio.Event()

    if not os.path.exists(args.config):
        print(f"Error: config file not found: {args.config}")
        sys.exit(1)

    simulation_dir = os.path.dirname(args.config) or "."
    setup_oasis_logging(os.path.join(simulation_dir, "log"))

    runner = RedditSimulationRunner(
        config_path=args.config,
        wait_for_commands=not args.no_wait
    )
    await runner.run(max_rounds=args.max_rounds)


def setup_signal_handlers():
    """Set up SIGTERM/SIGINT handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        global _cleanup_done
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        print(f"\nReceived {sig_name}, shutting down...")
        if not _cleanup_done:
            _cleanup_done = True
            if _shutdown_event:
                _shutdown_event.set()
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
        print("\nInterrupted")
    except SystemExit:
        pass
    finally:
        print("Simulation process exited")

