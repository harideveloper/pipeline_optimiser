"""
Fixer Agent - Applies suggested optimisations to CI/CD pipeline YAML.
"""

import logging
import yaml
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema.output_parser import StrOutputParser

logger = logging.getLogger(__name__)


class FixerAgent:
    """
    Applies suggested fixes to a CI/CD pipeline YAML file.
    Ensures output is valid YAML and adheres strictly to the requested changes.
    """

    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0):
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature)

        # Prompt template for structured LLM response
        self.prompt_template = PromptTemplate(
            input_variables=["pipeline_yaml", "suggested_fixes"],
            template=(
                "You are a CI/CD pipeline optimisation expert.\n\n"
                "Apply the suggested fixes to the following pipeline YAML. "
                "Return ONLY the optimised YAML content, with no explanations, comments, or markdown.\n\n"
                "Original Pipeline YAML:\n"
                "```yaml\n{pipeline_yaml}\n```\n\n"
                "Suggested Fixes:\n{suggested_fixes}\n\n"
                "Return optimised YAML:"
            )
        )

        # LCEL chain: prompt -> LLM -> string output
        self.chain = self.prompt_template | self.llm | StrOutputParser()
        logger.info("Initialised FixerAgent with model: %s", model_name)

    # ========================================================================
    # MAIN EXECUTION METHOD
    # ========================================================================
    def run(self, pipeline_yaml: str, suggested_fixes: list) -> str:
        """
        Apply suggested fixes to pipeline YAML.

        Args:
            pipeline_yaml: Original pipeline YAML content.
            suggested_fixes: List of suggested fixes to apply.

        Returns:
            Optimised YAML string (falls back to original if errors occur).
        """
        logger.info("Starting FixerAgent.run()")
        logger.debug("Input YAML length: %d, Fix count: %d", len(pipeline_yaml or ""), len(suggested_fixes or []))

        # Input validation
        if not pipeline_yaml or not pipeline_yaml.strip():
            logger.warning("Empty pipeline YAML provided; returning placeholder.")
            return "# No original YAML provided to rewrite."

        if not suggested_fixes:
            logger.info("No suggested fixes provided; returning original YAML.")
            return pipeline_yaml

        # Format fixes as enumerated list
        fixes_text = "\n".join(f"{i+1}. {fix}" for i, fix in enumerate(suggested_fixes))
        logger.debug("Formatted %d fixes for input prompt", len(suggested_fixes))

        try:
            # Execute LLM chain
            result = self.chain.invoke({
                "pipeline_yaml": pipeline_yaml,
                "suggested_fixes": fixes_text
            })
            optimised_yaml = self._clean_yaml_output(result)

            # Validate YAML syntax
            try:
                yaml.safe_load(optimised_yaml)
                logger.info("Optimised YAML validated successfully; length=%d", len(optimised_yaml))
            except yaml.YAMLError as e:
                logger.warning("Generated YAML invalid: %s; returning original YAML", e)
                return pipeline_yaml

            return optimised_yaml

        except Exception as e:
            logger.error("Error generating optimised YAML: %s", str(e), exc_info=True)
            return pipeline_yaml

    # -------------------------
    # Internal helpers
    # -------------------------
    def _clean_yaml_output(self, text: str) -> str:
        """
        Remove markdown formatting or extra whitespace from LLM output.
        """
        cleaned = text.strip()
        if cleaned.startswith("```yaml"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()
