import asyncio
import json
import os
import threading

from openai import OpenAI
from dotenv import load_dotenv
from fastmcp import Client
from pathlib import Path
from typing import Any, Dict, List, Tuple

load_dotenv()

# Default to local Ollama if no OPENAI_API_KEY is set
_api_key = os.environ.get("OPENAI_API_KEY", "ollama")
_base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1")
openai_client = OpenAI(api_key=_api_key, base_url=_base_url)

SYSTEM_PROMPT = """
You are a coding assistant whose goal it is to help us solve coding tasks. 
You have access to a series of tools you can execute. Here are the tools you can execute:

{tool_list_repr}

Your current working directory is: {cwd}
Use paths relative to this directory (e.g. "week1" or "week1/rag.py"). Do NOT invent absolute paths like "/home/user/...".

When you want to use a tool, reply with exactly one line in the format: tool: TOOL_NAME({{JSON_ARGS}}) and nothing else.
Use compact single-line JSON with double quotes, for example:
  tool: list_files({{"path": "week1"}})
  tool: read_file({{"filename": "week1/rag.py"}})
After receiving a tool_result(...) message, continue the task.
If no tool is needed, respond normally.
"""


YOU_COLOR = "\u001b[94m"
ASSISTANT_COLOR = "\u001b[93m"
RESET_COLOR = "\u001b[0m"

_MCP_SERVER = Path(__file__).parent / "simple_mcp.py"
_mcp_client = None
_mcp_loop = None

def _loop():
    global _mcp_loop
    if _mcp_loop is None:
        _mcp_loop = asyncio.new_event_loop()
        threading.Thread(target=_mcp_loop.run_forever, daemon=True).start()
    return _mcp_loop

async def _get_client():
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = Client(_MCP_SERVER)
        await _mcp_client.__aenter__()
    return _mcp_client

def _call_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, _loop()).result()

def get_full_system_prompt():
    async def _build():
        client = await _get_client()
        tools = await client.list_tools()
        tool_str_repr = ""
        for t in tools:
            tool_str_repr += (
                f"TOOL\n===\nName: {t.name}\n"
                f"Description: {t.description}\n"
                f"Args: {json.dumps(t.input_schema)}\n"
            )
            tool_str_repr += f'\n{"="*15}\n'
        return SYSTEM_PROMPT.format(tool_list_repr=tool_str_repr, cwd=str(Path.cwd()))
    return _call_async(_build())

def call_mcp_tool(name: str, args: Dict[str, Any]):
    async def _do():
        client = await _get_client()
        actual = name if name.endswith("_tool") else name + "_tool"
        return await client.call_tool(actual, args)
    return _call_async(_do())

def extract_tool_invocations(text: str) -> List[Tuple[str, Dict[str, Any]]]:
    invocations = []
    in_tool_block = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            line = line[3:].strip()
            if line == "" or (line.startswith("tool") and "(" not in line):
                in_tool_block = not in_tool_block
                continue
            if line.startswith("tool"):
                line = line[4:].lstrip(":").strip()
        elif line.startswith("tool:"):
            line = line[len("tool:"):].strip()
        elif not in_tool_block:
            continue
        try:
            if "(" not in line:
                continue
            name, rest = line.split("(", 1)
            name = name.strip().removesuffix("_tool")
            if not rest.endswith(")"):
                continue
            args = json.loads(rest[:-1].strip())
            invocations.append((name, args))
        except Exception:
            continue
    return invocations

def execute_llm_call(conversation: List[Dict[str, str]]):
    response = openai_client.chat.completions.create(
        model=os.environ.get("MODEL_NAME", "mistral-nemo:12b"),
        messages=conversation,
        max_completion_tokens=2000
    )
    return response.choices[0].message.content

def run_coding_agent_loop():
    print(get_full_system_prompt())
    conversation = [{
        "role": "system",
        "content": get_full_system_prompt()
    }]
    while True:
        try:
            user_input = input(f"{YOU_COLOR}You:{RESET_COLOR}:")
        except (KeyboardInterrupt, EOFError):
            break
        conversation.append({
            "role": "user",
            "content": user_input.strip()
        })
        while True:
            assistant_response = execute_llm_call(conversation)
            tool_invocations = extract_tool_invocations(assistant_response)
            if not tool_invocations:
                print(f"{ASSISTANT_COLOR}Assistant:{RESET_COLOR}: {assistant_response}")
                conversation.append({
                    "role": "assistant",
                    "content": assistant_response
                })
                break
            for name, args in tool_invocations:
                print(name, args)
                try:
                    result = call_mcp_tool(name, args)
                    resp = [c.model_dump() for c in result.content]
                except Exception as e:
                    resp = {"error": str(e)}
                conversation.append({
                    "role": "user",
                    "content": f"tool_result({json.dumps(resp, default=str)})"
                })
                

if __name__ == "__main__":
    run_coding_agent_loop()