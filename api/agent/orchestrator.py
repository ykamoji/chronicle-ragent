import os
import re
import logging
import time
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
- summary[chapter]: Retrieves the summary of a specific chapter.

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

def extract_action(text: str):
    """Parses the LLM output to find the Action."""
    match = re.search(r"Action:\s*(\w+)\[(.*?)\]", text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return None, None

def run_agent(session_id: str, query: str, max_steps: int = 10) -> str:
    """Executes the ReAct loop until 'finish' is called or max_steps is reached."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Error: GEMINI_API_KEY is not set."
        
    client = genai.Client(api_key=api_key)
    
    # Initialize conversation if needed
    history_objs = memory.get_history(session_id)
    if not history_objs:
        # We start a new prompt
        prompt = f"{SYSTEM_PROMPT}\n\nUser Question: {query}\n"
    else:
        # Reconstruct history for the LLM
        history_str = ""
        for msg in history_objs:
            role = msg["role"].capitalize()
            content = msg["content"]
            history_str += f"{role}: {content}\n"
        
        prompt = f"{SYSTEM_PROMPT}\n\n{history_str}User Question: {query}\n"

    memory.add_message(session_id, "User", query)
    
    current_prompt = prompt
    
    for step in range(max_steps):
        logger.info(f"Agent Step {step + 1}/{max_steps}")
        
        # Call Gemini
        try:
            # Note: We append 'Thought:' at the end to encourage the model to start reasoning
            response = client.models.generate_content(
                model='gemma-4-31b-it',
                contents=current_prompt + "Thought:",
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    # We can use stop sequences to ensure it stops before hallucinating observations
                    stop_sequences=["Observation:"]
                )
            )
            llm_text = response.text.strip()
            # Ensure "Thought:" is prepended since we appended it to the prompt mechanically
            if not llm_text.startswith("Thought:"):
                llm_text = "Thought: " + llm_text
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return f"Agent failed due to LLM error: {e}"

        logger.info(f"LLM Response:\n{llm_text}")
        # Mark LLM reasoning as hidden so it doesn't clutter the user facing chat
        memory.add_message(session_id, "Agent", llm_text, is_hidden=True)
        current_prompt += llm_text + "\n"

        tool_name, tool_arg = extract_action(llm_text)
        
        if not tool_name:
            # Model didn't output an action correctly
            logger.warning("No action found in LLM response.")
            observation = "System Error: No valid Action format found. Use tool_name[arg] or finish[answer]."
            current_prompt += f"Observation: {observation}\n"
            continue
            
        if tool_name.lower() == "finish":
            # This is the final answer, so we add a visible Agent message
            memory.add_message(session_id, "Agent", tool_arg, is_hidden=False)
            return tool_arg

        # Run the tool
        if tool_name in TOOLS:
            observation = TOOLS[tool_name](tool_arg)
        else:
            observation = f"System Error: Tool '{tool_name}' not found. Available tools: {', '.join(TOOLS.keys())}, finish"

        logger.info(f"Observation length: {len(str(observation))} characters")
        
        # Append observation and loop
        obs_text = f"Observation: {observation}\n"
        current_prompt += obs_text
        memory.add_message(session_id, "System", obs_text.strip(), is_hidden=True)

        time.sleep(10)

    final_msg = "Agent reached maximum steps without finding a final answer."
    logger.warning(final_msg)
    return final_msg


def run_agent_stream(session_id: str, query: str, max_steps: int = 10):
    """Generator version of run_agent that yields SSE events at each step."""
    import json

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        yield json.dumps({"type": "error", "content": "GEMINI_API_KEY is not set."})
        return

    client = genai.Client(api_key=api_key)

    try:
        # Initialize conversation
        history_objs = memory.get_history(session_id)
        if not history_objs:
            prompt = f"{SYSTEM_PROMPT}\n\nUser Question: {query}\n"
        else:
            history_str = ""
            for msg in history_objs:
                role = msg["role"].capitalize()
                content = msg["content"]
                history_str += f"{role}: {content}\n"
            prompt = f"{SYSTEM_PROMPT}\n\n{history_str}User Question: {query}\n"

        memory.add_message(session_id, "User", query)
        current_prompt = prompt

        for step in range(max_steps):
            logger.info(f"Agent Step {step + 1}/{max_steps}")
            yield json.dumps({"type": "step", "step": step + 1, "max_steps": max_steps})

            # Call LLM
            try:
                response = client.models.generate_content(
                    model='gemma-4-31b-it',
                    contents=current_prompt + "Thought:",
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        stop_sequences=["Observation:"]
                    )
                )
                llm_text = response.text.strip()
                if not llm_text.startswith("Thought:"):
                    llm_text = "Thought: " + llm_text
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                memory.add_message(session_id, "Agent", f"LLM Error: {e}", is_hidden=True)
                yield json.dumps({"type": "error", "content": f"LLM error: {e}"})
                return

            logger.info(f"LLM Response:\n{llm_text}")
            memory.add_message(session_id, "Agent", llm_text, is_hidden=True)
            current_prompt += llm_text + "\n"

            # Parse the thought text
            thought_match = re.search(r"Thought:\s*(.*?)(?=Action:|$)", llm_text, re.DOTALL)
            thought_text = thought_match.group(1).strip() if thought_match else llm_text

            tool_name, tool_arg = extract_action(llm_text)

            # Yield thought event
            yield json.dumps({
                "type": "thought",
                "content": thought_text,
                "action": f"{tool_name}[{tool_arg}]" if tool_name else None
            })

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
                    "session_id": session_id
                })
                return

            # Yield tool call event
            yield json.dumps({"type": "tool", "tool": tool_name, "args": tool_arg})

            # Run the tool
            if tool_name in TOOLS:
                observation = TOOLS[tool_name](tool_arg)
            else:
                observation = f"System Error: Tool '{tool_name}' not found. Available tools: {', '.join(TOOLS.keys())}, finish"

            logger.info(f"Observation length: {len(str(observation))} characters")

            obs_text = f"Observation: {observation}\n"
            current_prompt += obs_text
            memory.add_message(session_id, "System", obs_text.strip(), is_hidden=True)

            # Yield observation summary (truncated for display)
            obs_display = str(observation)[:200] + ("..." if len(str(observation)) > 200 else "")
            yield json.dumps({"type": "observation", "content": obs_display})

            time.sleep(10)

        final_msg = "Agent reached maximum steps without finding a final answer."
        logger.warning(final_msg)
        yield json.dumps({"type": "answer", "content": final_msg, "session_id": session_id})

    except Exception as e:
        logger.error(f"Agent stream error: {e}")
        yield json.dumps({"type": "error", "content": f"Agent error: {e}"})
