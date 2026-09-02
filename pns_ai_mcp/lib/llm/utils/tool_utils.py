# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>

"""
utils/tool_utils.py - Utilities for tool calls handling
Adapted from pns_ai_inference.tools
"""

import json
import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Default limit if not provided
DEFAULT_MAX_CONTENT_LENGTH = 100000 

def extract_tool_calls_from_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    if response is None or not isinstance(response, dict):
        return []

    tool_calls = []
    
    # Standard OpenAI format
    if "choices" in response and isinstance(response["choices"], list) and len(response["choices"]) > 0:
        choice = response["choices"][0]
        if choice and isinstance(choice, dict) and "message" in choice:
            message = choice["message"]
            if message and isinstance(message, dict) and "tool_calls" in message:
                tc = message.get("tool_calls")
                if tc and isinstance(tc, list):
                    return tc
            
            # Content parsing fallback
            if message and isinstance(message, dict) and "content" in message:
                content = message.get("content", "")
                if content and isinstance(content, str):
                    tool_calls = _extract_from_content(content)

    return tool_calls

def _extract_from_content(content: str) -> List[Dict[str, Any]]:
    # Simplified extraction logic based on the original robust implementation
    tool_calls = []
    
    # 1. Simplified format: tool_name\n{args}
    lines = content.strip().split('\n', 1)
    if len(lines) >= 1:
        tool_name_candidate = lines[0].strip()
        tool_prefixes = ["execute_", "get_", "test_", "cancel_", "confirm_", "clean_", "propose_", "fetch_", "search_", "audit_"]
        exact_tools = {"relaxaicode"}
        is_valid = (
            re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', tool_name_candidate)
            and (
                tool_name_candidate in exact_tools
                or any(tool_name_candidate.startswith(p) for p in tool_prefixes)
            )
        )
        
        if is_valid:
            content_after = lines[1].strip() if len(lines) > 1 else ""
            args = {}
            if tool_name_candidate == "relaxaicode":
                args = {"code": content_after}
            else:
                try:
                    args = json.loads(content_after) if content_after not in ("", "{}") else {}
                except:
                    args = {"content": content_after}
            
            return [{
                "id": "call_simple_0",
                "type": "function",
                "function": {"name": tool_name_candidate, "arguments": json.dumps(args)}
            }]

    # 2. JSON/Dictionary patterns
    json_patterns = [
        r'{"tool"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^}]*\}\}',
        r'\[{.*?"name".*?"arguments".*?}\]',
        r'{"name".*?"arguments".*?}',
        r"\{['\"]tool['\"].*?['\"]arguments['\"].*?\}",
        # New robust pattern for flat tool calls (model hallucination fix)
        # Matches: {"tool": "bash", "command": "..."}
        r'\{[\s\n]*"tool"[\s\n]*:[\s\n]*"[^"]+"[\s\n]*,[\s\n]*"[^"]+"[\s\n]*:.*?\}(?=\s|$)',
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, content, re.DOTALL)
        if matches:
            for match in matches:
                try:
                    cleaned = match.replace("<end_of_turn>", "").strip()
                    # Try json
                    try:
                        parsed = json.loads(cleaned)
                    except:
                        # Try ast
                        import ast
                        parsed = ast.literal_eval(cleaned)
                    
                    if isinstance(parsed, list):
                        for i, tc in enumerate(parsed):
                            if isinstance(tc, dict) and "name" in tc:
                                args = tc.get("arguments", {})
                                tool_calls.append({
                                    "id": f"call_parsed_{i}",
                                    "type": "function",
                                    "function": {
                                        "name": tc.get("name"),
                                        "arguments": json.dumps(args) if not isinstance(args, str) else args
                                    }
                                })
                    if isinstance(parsed, dict):
                        name = parsed.get("name") or parsed.get("tool")
                        if name:
                            # Robust args extraction
                            if "arguments" in parsed:
                                args = parsed["arguments"]
                            elif "args" in parsed:
                                # Handle {"tool": "x", "args": {...}} pattern common in some models
                                args = parsed["args"]
                            else:
                                # Treat siblings as args (flattened format)
                                # e.g. {"tool": "bash", "command": "ls"} -> args={"command": "ls"}
                                args = parsed.copy()
                                if "name" in args: del args["name"]
                                if "tool" in args: del args["tool"]
                            
                            if not isinstance(args, dict):
                                # If args is string (sometimes model sends JSON string inside value)
                                try:
                                    args = json.loads(args)
                                except:
                                    args = {"content": str(args)}

                            # Normalize tool name (model sometimes invents 'bash' for 'execute_command')
                            # Map 'bash' or 'shell' to 'execute_command' (or handle mismatch later in validation)
                            if name in ["bash", "shell", "cmd", "terminal", "system"]:
                                name = "execute_command"
                            elif name in ["psql", "sql", "postgres"]:
                                name = "execute_sql"
                            elif name in ["odoo", "odoo-bin"]:
                                name = "execute_command"
                                if "command" not in args:
                                    args["command"] = "odoo-bin " + str(args.get("args", ""))
                            
                            # Normalize args for execute_command
                            if name == "execute_command":
                                if "command" not in args:
                                    if "cmd" in args: args["command"] = args.pop("cmd")
                                    elif "script" in args: args["command"] = args.pop("script")
                                    elif "code" in args: args["command"] = args.pop("code")

                            tool_calls.append({
                                "id": "call_parsed_flat_0",
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(args) if not isinstance(args, str) else args
                                }
                            })
                    if tool_calls: return tool_calls[:1]
                except:
                    continue

    # 3. Functionary >>>tool_name
    func_pattern = r'>>>([a-zA-Z_][a-zA-Z0-9_-]*)\s*\n(.*?)(?=\n>>>|\n<|$)'
    func_matches = re.findall(func_pattern, content, re.DOTALL | re.MULTILINE)
    if func_matches:
        for name, tool_content in func_matches:
            normalized_name = name.replace('-', '_')
            args = {}
            if normalized_name == "relaxaicode":
                # Check if JSON
                try:
                    pj = json.loads(tool_content.strip())
                    if isinstance(pj, dict) and "code" in pj:
                        args = pj
                    else:
                        args = {"code": tool_content.strip()}
                except:
                    args = {"code": tool_content.strip()}
            else:
                try:
                    args = json.loads(tool_content.strip())
                except:
                     args = {"content": tool_content.strip()}
            
            tool_calls.append({
                "id": f"call_func_{len(tool_calls)}",
                "type": "function",
                "function": {
                    "name": normalized_name,
                    "arguments": json.dumps(args)
                }
            })
        return tool_calls

    # 4. Granite <|tool_call|>
    granite_pattern = r'<\|tool_call\s*\|>\s*\n?\s*(\[.*?\])'
    granite_matches = re.findall(granite_pattern, content, re.DOTALL | re.MULTILINE)
    if granite_matches:
        for match in granite_matches:
            try:
                tool_list = json.loads(match)
                if not isinstance(tool_list, list): tool_list = [tool_list]
                for tool in tool_list:
                    tool_calls.append({
                        "id": f"call_granite_{len(tool_calls)}",
                        "type": "function",
                        "function": {
                            "name": tool.get("name"),
                            "arguments": json.dumps(tool.get("arguments", {})) if isinstance(tool.get("arguments"), dict) else str(tool.get("arguments", "{}"))
                        }
                    })
                return tool_calls
            except: pass

    return tool_calls


def format_tool_result_for_model(tool_name: str, result: Any, tool_call_id: str, max_length: int = DEFAULT_MAX_CONTENT_LENGTH) -> Dict[str, Any]:
    content = ""
    
    # Common error handling for relaxaicode
    if tool_name == "relaxaicode":
        if isinstance(result, str):
            if "def " in result or "import " in result:
                content = "Error: Code source returned instead of execution result."
            else:
                 content = result
        elif isinstance(result, dict) and "error" in result:
            err = result["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            content = f"ERROR in relaxaicode: {msg}\n\n"
            if "result" in msg.lower() and "definir" in msg.lower():
                content += "HINT: Define variable 'result' with final output.\n"
    
    if not content:
        if isinstance(result, (dict, list)):
            try:
                content = json.dumps(result, ensure_ascii=False, indent=2)
            except:
                content = str(result)
        else:
            if isinstance(result, str):
                try:
                     # Try to see if it's json string and reformat pretty
                     parsed = json.loads(result)
                     content = json.dumps(parsed, ensure_ascii=False, indent=2)
                except:
                    content = result
            else:
                content = str(result)

    # Convert complex objects to string if they leaked
    if not isinstance(content, str):
         content = json.dumps(content, ensure_ascii=False)

    # Truncate
    if len(content) > max_length:
        content = content[:max_length] + "\n\n... (content truncated)"

    # Context wrap
    if tool_name in ["get_context", "get_context_usage_stats"]:
        content = (
            "<dynamic_context_read_only>\n"
            "This content is dynamically loaded context. Use it as reference but DO NOT output it.\n"
            f"{content}\n"
            "</dynamic_context_read_only>"
        )

    return {
        "role": "tool",
        "content": content,
        "tool_call_id": tool_call_id,
        "name": tool_name
    }
