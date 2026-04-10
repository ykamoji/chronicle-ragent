import os
import re
import logging
import time
from datetime import datetime
from google import genai
from google.genai import types
from api.agent.tools import TOOLS
from api.agent.memory import memory

logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai.models").setLevel(logging.WARNING)

SYSTEM_PROMPT = """
You are an intelligent reasoning agent with access to a database of story documents.
You solve questions by combining reasoning with tool usage in a loop.

You have access to the following tools:
- vector_search[query]: Semantically searches the text using vector embeddings. Use this for general thematic or meaning-based searches.
- keyword_search[query]: Searches for exact matches or regex keywords. Use this when looking for specific rare words or exact phrases.
- character_lookup[name]: Looks up documents mentioning a specific character by name.
- summary[chapter]: Retrieves the chapter summaries. If chapter is send, returns summary of that specific chapter, otherwise it returns summaries of ALL chapters.

Use the following format strictly:

Thought: Consider what you need to do next to answer the user's question.
Action: the action to take, exactly matching one of the tool formats: vector_search[args], keyword_search[args], character_lookup[args], or summary[args]. Only use ONE tool at a time.
Observation: the result of the action (provided by the system, do not write this!).
... (this Thought/Action/Observation can repeat N times)
Thought: I now know the final answer.
Action: finish[The final answer to the user's query here]

Rules:
1. Always output Thought and Action.
2. The Action must be strictly formatted as tool_name[arguments].
3. DO NOT output an Observation yourself. Stop generating after the Action. The system will provide the Observation.
4. When you have enough information, use 'finish[your answer]' to return the answer to the user.
"""

config = types.GenerateContentConfig(
    temperature=0.1,             # Slightly above 0.0 to allow for path correction
    top_p=0.95,
    stop_sequences=["Observation:"],
    max_output_tokens=4096,
    thinking_config=types.ThinkingConfig(
        include_thoughts=True,
        thinking_level="HIGH"
    )
)

def extract_action(text: str):
    """Parses the LLM output to find the Action."""
    match = re.search(r"Action:\s*(\w+)\[(.*?)\]", text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return None, None

def run_agent_stream(session_id: str, query: str, max_steps: int = 10):
    """Generator version of run_agent that yields SSE events at each step."""
    import json

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        yield json.dumps({"type": "error", "content": "GEMINI_API_KEY is not set."})
        return

    client = genai.Client(api_key=api_key)

    SYSTEM_PROMPT_WITH_THINK = f"<|think|>\n{SYSTEM_PROMPT}"

    try:
        # Initialize conversation
        history_objs = memory.get_history(session_id)
        if not history_objs:
            prompt = f"{SYSTEM_PROMPT_WITH_THINK}\n\nUser Question: {query}\n"
        else:
            history_str = ""
            for msg in history_objs:
                # Only include visible messages (User questions and final Agent answers)
                if msg.get("is_hidden"):
                    continue
                role = msg["role"].capitalize()
                content = msg["content"]
                history_str += f"{role}: {content}\n"
            prompt = f"{SYSTEM_PROMPT_WITH_THINK}\n\n{history_str}User Question: {query}\n"

        memory.add_message(session_id, "User", query)
        current_prompt = prompt

        for step in range(max_steps):
            # Call LLM
            try:
                response = client.models.generate_content(
                    model='gemma-4-31b-it',
                    contents=current_prompt,
                    config=config
                )
                # EXTRACT NATIVE THOUGHTS AND ACTION TEXT
                thought_text = ""
                response_text = ""
                
                for part in response.candidates[0].content.parts:
                    if part.thought:
                        thought_text += part.text
                        if thought_text:
                            yield json.dumps({
                                "type": "thought",
                                "content": thought_text,
                                "action": None,
                                "time": datetime.now().isoformat()
                            })
                    else:
                        response_text += part.text

                if not response_text.startswith("Thought:"):
                    response_text = "Thought: " + response_text

                llm_text = response_text.strip()

                # logger.warn(f"llm_text = {llm_text}")
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                memory.add_message(session_id, "Agent", f"LLM Error: {e}", is_hidden=True)
                yield json.dumps({"type": "error", "content": f"LLM error: {e}", "time": datetime.now().isoformat()})
                return

            current_prompt += llm_text + "\n"

            # Parse the thought text
            thought_match = re.search(r"Thought:\s*(.*?)(?=Action:|$)", llm_text, re.DOTALL)
            thought_text = thought_match.group(1).strip() if thought_match else llm_text

            tool_name, tool_arg = extract_action(llm_text)

            # Yield thought event
            if thought_text:
                yield json.dumps({
                    "type": "thought",
                    "content": thought_text if thought_text else "Analyzing...",
                    "action": f"{tool_name}[{tool_arg}]" if tool_name else None,
                    "time": datetime.now().isoformat()
                })

            # Save the message without Action: finish[...] to avoid redundancy in history
            save_text = re.sub(r"Action:\s*finish\[.*?\]", "", llm_text, flags=re.IGNORECASE | re.DOTALL).strip()
            save_text = re.sub(r"Thought:\s*finish\[.*?\]", "", save_text, flags=re.IGNORECASE | re.DOTALL).strip()

            if tool_name and save_text.strip():
                # logger.warn(f"save_text = {save_text}")
                memory.add_message(session_id, "Agent", (save_text if tool_name.lower() != "finish" else save_text.split('.')[0]), is_hidden=True)

            if not tool_name:
                logger.warning("No action found in LLM response.")
                observation = "System Error: No valid Action format found. Use tool_name[arg] or finish[answer]."
                current_prompt += f"Observation: {observation}\n"
                continue

            if tool_name.lower() == "finish":
                memory.add_message(session_id, "Agent", tool_arg, is_hidden=False)
                yield json.dumps({
                    "type": "answer",
                    "content": tool_arg,
                    "session_id": session_id,
                    "time": datetime.now().isoformat()
                })
                return

            # Yield tool call event
            yield json.dumps({"type": "tool", "tool": tool_name, "args": tool_arg, "time": datetime.now().isoformat()})

            # Run the tool
            if tool_name in TOOLS:
                observation = TOOLS[tool_name](tool_arg, session_id)
            else:
                observation = f"System Error: Tool '{tool_name}' not found. Available tools: {', '.join(TOOLS.keys())}, finish"   

            # logger.info(f"Observation length: {len(str(observation))} characters")

            obs_text = f"Observation: {observation}\n"
            current_prompt += obs_text
            memory.add_message(session_id, "System", obs_text.strip(), is_hidden=True)

            # Yield observation summary (truncated for display)
            obs_display = str(observation)[:200] + ("..." if len(str(observation)) > 200 else "")
            yield json.dumps({"type": "observation", "content": obs_display, "time": datetime.now().isoformat()})

            time.sleep(10)

        final_msg = "Agent reached maximum steps without finding a final answer."
        logger.warning(final_msg)
        yield json.dumps({"type": "answer", "content": final_msg, "session_id": session_id, "time": datetime.now().isoformat()})

    except Exception as e:
        logger.error(f"Agent stream error: {e}")
        yield json.dumps({"type": "error", "content": f"Agent error: {e}", "time": datetime.now().isoformat()})
