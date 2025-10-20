"""
Fixer Agent - Applies suggested optimisations to CI/CD pipeline YAML.
"""

from typing import Dict, Any, Optional
import yaml

from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema.output_parser import StrOutputParser

from app.components.base_service import BaseService
from app.utils.logger import get_logger

logger = get_logger(__name__, "Fixer")


class Fixer(BaseService):
    """
    Applies suggested fixes to a CI/CD pipeline YAML file.
    Ensures output is valid YAML and adheres strictly to the requested changes.
    """

    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0):
        super().__init__(agent_name="fix")
        
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature)

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

        self.chain = self.prompt_template | self.llm | StrOutputParser()
        logger.debug("Initialised Fixer: model=%s" % model_name, correlation_id="INIT")

    def run(self, pipeline_yaml: str, suggested_fixes: list, correlation_id: Optional[str] = None) -> str:
        """Apply suggested fixes to pipeline YAML."""

        if not pipeline_yaml or not pipeline_yaml.strip():
            logger.error("Empty pipeline YAML provided", correlation_id=correlation_id)
            return "# No original YAML provided"

        if not suggested_fixes:
            logger.debug("No fixes to apply, returning original", correlation_id=correlation_id)
            return pipeline_yaml

        logger.debug("Applying %d fixes" % len(suggested_fixes), correlation_id=correlation_id)

        try:
            fixes_text = "\n".join(f"{i+1}. {fix}" for i, fix in enumerate(suggested_fixes))
            
            result = self.chain.invoke({
                "pipeline_yaml": pipeline_yaml,
                "suggested_fixes": fixes_text
            })
            
            optimised_yaml = self._clean_yaml_output(result)

            try:
                yaml.safe_load(optimised_yaml)
                logger.info("Applied %d fixes successfully" % len(suggested_fixes), correlation_id=correlation_id)
            except yaml.YAMLError as e:
                logger.warning("Generated YAML invalid, returning original: %s" % str(e), correlation_id=correlation_id)
                return pipeline_yaml

            return optimised_yaml

        except Exception as e:
            logger.error("Failed to generate optimised YAML: %s" % str(e), correlation_id=correlation_id)
            return pipeline_yaml

    def _execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute fixer within workflow"""
        correlation_id = state.get("correlation_id")
        
        suggested_fixes = state["analysis_result"].get("suggested_fixes", [])

        if not suggested_fixes:
            state["error"] = "No fixes to apply"
            logger.warning("No fixes to apply", correlation_id=correlation_id)
            return state

        optimised = self.run(
            pipeline_yaml=state["pipeline_yaml"],
            suggested_fixes=suggested_fixes,
            correlation_id=correlation_id
        )

        if optimised and len(optimised) > 50:
            state["optimised_yaml"] = optimised
        else:
            state["error"] = "Fixer returned invalid output"
            logger.error("Invalid output from fixer", correlation_id=correlation_id)

        return state

    def _get_artifact_key(self) -> Optional[str]:
        """Optimised YAML should be saved as artifact"""
        return "optimised_yaml"

    def _clean_yaml_output(self, text: str) -> str:
        """Remove markdown formatting from LLM output"""
        cleaned = text.strip()
        if cleaned.startswith("```yaml"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()