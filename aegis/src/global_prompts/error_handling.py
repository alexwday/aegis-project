# global_prompts/error_handling.py
"""
Shared Error Handling Statement

Provides centralized error handling guidelines to reduce redundancy across agent prompts.
"""

import logging

logger = logging.getLogger(__name__)


def get_error_handling_statement(agent_type: str = 'default') -> str:
    """
    Returns error handling guidelines for agents.
    
    Args:
        agent_type: Type of agent ('router', 'clarifier', 'planner', 'summarizer', 'default')
    
    Returns:
        str: Formatted error handling guidelines
    """
    base_statement = """<ERROR_HANDLING>
<GENERAL_PRINCIPLES>
- When facing ambiguity, choose the most likely interpretation based on context
- Make reasonable assumptions when non-critical information is missing
- Never fabricate data or information
- Signal confidence levels appropriately
</GENERAL_PRINCIPLES>

<CONFIDENCE_SIGNALING>
- HIGH CONFIDENCE: Proceed normally
- MEDIUM CONFIDENCE: Proceed with noted uncertainties
- LOW CONFIDENCE: Acknowledge significant uncertainty
</CONFIDENCE_SIGNALING>
"""
    
    # Add agent-specific handling if needed
    agent_specific = {
        'router': """
<ROUTER_SPECIFIC>
- If ambiguous between research/direct, ask: Does this need NEW data? → Research
- Default to research ONLY when specific data or sources are likely needed
- For multiple questions, route based on primary intent
</ROUTER_SPECIFIC>""",
        
        'clarifier': """
<CLARIFIER_SPECIFIC>
- When time references are ambiguous, request confirmation
- For unclear bank references, list possible interpretations
- If scope is too broad, ask for prioritization
</CLARIFIER_SPECIFIC>""",
        
        'planner': """
<PLANNER_SPECIFIC>
- When unsure about database relevance, include it with lower priority
- For broad queries, select all potentially relevant databases
- Clearly indicate confidence in database selections
</PLANNER_SPECIFIC>""",
        
        'summarizer': """
<SUMMARIZER_SPECIFIC>
- When data conflicts, present all versions with sources
- For incomplete results, clearly indicate what's missing
- Maintain source attribution even under uncertainty
</SUMMARIZER_SPECIFIC>"""
    }
    
    if agent_type in agent_specific:
        base_statement += agent_specific[agent_type]
    
    base_statement += "\n</ERROR_HANDLING>"
    
    return base_statement