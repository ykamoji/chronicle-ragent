import re
import logging
from google import genai
from google.genai import types
from api.agent.tools import TOOLS
from api.agent.memory import memory
from api.config import settings

logger = logging.getLogger(__name__)

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

def run_agent(session_id: str, query: str, max_steps: int = 5) -> str:
    """Executes the ReAct loop until 'finish' is called or max_steps is reached."""
    if not settings.gemini_api_key:
        return "Error: GEMINI_API_KEY is not set."
        
    client = genai.Client(api_key=settings.gemini_api_key)
    
    # Initialize conversation if needed
    history = memory.get_history(session_id)
    if not history:
        # We start a new prompt
        prompt = f"{SYSTEM_PROMPT}\n\nUser Question: {query}\n"
    else:
        # Reconstruct history
        prompt = f"{SYSTEM_PROMPT}\n\n" + "\n".join(history) + f"\nUser Question: {query}\n"

    memory.add_message(session_id, "User", query)
    
    current_prompt = prompt
    
    for step in range(max_steps):
        logger.info(f"Agent Step {step + 1}/{max_steps}")
        
        # Call Gemini
        try:
            # Note: We append 'Thought:' at the end to encourage the model to start reasoning
            response = client.models.generate_content(
                model='gemini-2.0-flash',
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
        memory.add_message(session_id, "Agent", llm_text)
        current_prompt += llm_text + "\n"

        tool_name, tool_arg = extract_action(llm_text)
        
        if not tool_name:
            # Model didn't output an action correctly
            logger.warning("No action found in LLM response.")
            observation = "System Error: No valid Action format found. Use tool_name[arg] or finish[answer]."
            current_prompt += f"Observation: {observation}\n"
            continue
            
        if tool_name.lower() == "finish":
            # We are done
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
        memory.add_message(session_id, "System", obs_text.strip())

    final_msg = "Agent reached maximum steps without finding a final answer."
    logger.warning(final_msg)
    return final_msg
