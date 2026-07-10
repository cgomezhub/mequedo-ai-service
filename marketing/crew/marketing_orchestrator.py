from .marketing_tasks import get_generate_content_task
from .marketing_agents import get_copywriter_agent
import os
import logging

from crewai import Crew

# Disable CrewAI Telemetry gracefully, preventing server DNS blocks natively.
os.environ["CREWAI_DISABLE_TELEMETRY"] = "1"


logger = logging.getLogger(__name__)


class MarketingCrew:
    """CrewAI orchestrator for marketing content generation.

    Single-agent flow: the copywriter drafts and self-validates the content in one
    pass, returning the ``MarketingContentSchema`` JSON for a single source
    document. The QA editor was removed because a second sequential 70B pass on
    the free-tier NVIDIA NIM endpoint blew past the hard job timeout, and its
    guarantees (correct price on the graphic, valid image URL, HTML stripping,
    data-quality flags) are already enforced deterministically in ``views.py``.
    Grounding now rests on the anti-hallucination prompt + those guards + human
    review of the resulting ``draft``.
    """

    def __init__(self) -> None:
        self.copywriter = get_copywriter_agent()
        self.agents = [self.copywriter]

        self.generate_task = get_generate_content_task(self.copywriter)
        self.tasks = [self.generate_task]

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
            # Prefer the copywriter task's structured JSON output when present.
            output = getattr(result, "json_dict", None)
            if output:
                import json
                return json.dumps(output)
            return str(result)
        except Exception as e:
            logger.error(f"Error executing MarketingCrew kickoff: {e}")
            raise
