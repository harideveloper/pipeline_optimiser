""" LLM Prompts for Pipeline Orchestration """

from typing import Dict, Any, List


RISK_ASSESSOR_SYSTEM_PROMPT = """You are a DevOps risk assessment expert analyzing pipeline optimisations.

  Your task is to evaluate the risk level of changes that have been applied to a CI/CD pipeline.

  Analyze the changes based on:
  1. **Severity of issues fixed** - Higher severity fixes = higher risk changes
  2. **Type of changes** - Some change types are riskier than others:
    - LOW RISK: Adding caching, documentation improvements
    - MEDIUM RISK: Changing dependencies, parallelization, resource limits
    - HIGH RISK: Modifying security settings, deployment logic, removing checks
  3. **Number of changes** - More changes = higher cumulative risk
  4. **Critical job modifications** - Changes to deploy/release jobs are high risk

  Provide your assessment in this JSON format:
  {
    "overall_risk": "low|medium|high",
    "risk_score": 0-10,
    "risks": [
      {
        "category": "category name",
        "description": "specific risk description",
        "severity": "low|medium|high",
        "mitigation": "how to mitigate this risk"
      }
    ],
    "recommendations": [
      "specific recommendation 1",
      "specific recommendation 2"
    ],
    "analysis": "Detailed analysis of the changes and their risk profile"
  }

  Risk scoring guide:
  - 0-3: Low risk - Minor optimisations, safe changes
  - 4-6: Medium risk - Moderate changes requiring review
  - 7-10: High risk - Significant changes requiring careful testing

  Be specific and actionable in your recommendations.
  """


def build_risk_context(
        issues: List[Dict[str, Any]],
        fixes: List[Dict[str, Any]],
        original_yaml: str,
        optimised_yaml: str,
        heuristic_score: float
    ) -> str:
        """
        Build detailed context for LLM risk assessment.
        
        Args:
            issues: Issues detected
            fixes: Fixes applied
            original_yaml: Original YAML
            optimised_yaml: optimised YAML
            heuristic_score: Pre-calculated heuristic risk score
            
        Returns:
            Formatted context string
        """
        # Format issues
        issues_text = "\n".join([
            f"- {i+1}. [{issue.get('severity', 'medium').upper()}] {issue['type']}: "
            f"{issue['description']} (at {issue.get('location', 'unknown')})"
            for i, issue in enumerate(issues)
        ])
        
        # Format fixes
        fixes_text = "\n".join([
            f"- {i+1}. {fix.get('fix', fix.get('description', str(fix)))}"
            for i, fix in enumerate(fixes)
        ])
        
        # Build context
        context = f"""# Risk Assessment Request

            ## Summary
            - **Issues Detected**: {len(issues)}
            - **Fixes Applied**: {len(fixes)}
            - **Heuristic Risk Score**: {heuristic_score:.1f}/10

            ## Issues Identified
            {issues_text}

            ## Changes Applied
            {fixes_text}

            ## YAML Comparison

            ### Original Pipeline (first 1000 chars)
            ```yaml
            {original_yaml[:1000]}
            ```

            ### optimised Pipeline (first 1000 chars)
            ```yaml
            {optimised_yaml[:1000]}
            ```

            ## Your Task
            Analyze these changes and provide a comprehensive risk assessment. Consider:
            1. What could break or behave unexpectedly?
            2. What security implications exist?
            3. What testing should be done before merging?
            4. Are there any rollback considerations?

            Provide specific, actionable recommendations.
        """
        
        return context