from .marketing_tasks import get_generate_content_task, get_qa_marketing_task
from .marketing_agents import get_copywriter_agent, get_brand_qa_agent
import os
import logging

from crewai import Crew

# Disable CrewAI Telemetry gracefully, preventing server DNS blocks natively.
os.environ["CREWAI_DISABLE_TELEMETRY"] = "1"


logger = logging.getLogger(__name__)


class MarketingCrew:
    """CrewAI orchestrator for marketing content generation.

    Shaped like ``MequedoCrew``: builds the copywriter + QA editor agents and a
    chained generate -> QA task flow, then runs ``kickoff`` returning the
    validated ``MarketingContentSchema`` JSON for a single source document.
    """

    def __init__(self) -> None:
        self.copywriter = get_copywriter_agent()
        self.editor = get_brand_qa_agent()
        self.agents = [self.copywriter, self.editor]

        self.generate_task = get_generate_content_task(self.copywriter)
        self.qa_task = get_qa_marketing_task(self.editor, self.generate_task)
        self.tasks = [self.generate_task, self.qa_task]

    def setup_crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            # Memory off (avoids OpenAI embedding init); cache on for cross-agent reuse.
            memory=False,
            cache=True,
            verbose=True,
        )

    def kickoff(self, inputs: dict, llm_override=None):
        """Run the crew and return the final validated marketing JSON string.

        ``inputs`` must contain ``source_type`` and ``source_id``. An optional
        ``llm_override`` swaps every agent's LLM (used by the retry fallback).
        """
        if llm_override is not None:
            logger.warning(
                f"MarketingCrew: Applying LLM override -> {getattr(llm_override, 'model', 'unknown')}")
            for agent in self.agents:
                agent.llm = llm_override

        crew = self.setup_crew()
        try:
            result = crew.kickoff(inputs=inputs)
            # Prefer the structured JSON output of the final QA task when present.
            output = getattr(result, "json_dict", None)
            if output:
                import json
                return json.dumps(output)
            return str(result)
        except Exception as e:
            logger.error(f"Error executing MarketingCrew kickoff: {e}")
            raise
