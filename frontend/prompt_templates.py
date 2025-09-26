"""
Centralized Prompt Templates for Nova Prompt Optimizer Frontend
"""

class PromptTemplates:
    """Centralized storage for all AI prompt templates used in the frontend"""
    
    @staticmethod
    def dataset_analysis(dataset_content: str, focus_areas: list, analysis_depth: str, prompt_content: str = None) -> str:
        """
        SIMPLIFIED DATASET ANALYSIS PROMPT
        
        Purpose: Analyzes dataset and prompt to understand intent and create appropriate metrics
        Focus: Dataset structure + Prompt intent = Simple, effective metrics
        """
        
        # Add prompt analysis if provided
        prompt_analysis_text = ""
        if prompt_content:
            prompt_analysis_text = f"""

PROMPT INTENT ANALYSIS:
The following is the original prompt that will be used with this dataset:
---
{prompt_content}
---

Analyze the prompt to understand:
1. What task is the AI being asked to perform?
2. What format should the output be in (JSON, text, classification, etc.)?
3. What are the key success criteria implied by the prompt?
4. How should responses be evaluated for quality?"""
        
        return f"""You are an expert in AI evaluation metrics. Analyze the dataset and prompt to create simple, effective evaluation metrics.

Dataset Content ({analysis_depth} analysis):
```
{dataset_content}
```

{prompt_analysis_text}

IMPORTANT CLARIFICATIONS:
- The dataset format (JSONL, CSV, etc.) is just how the data is stored - ignore this format
- Focus ONLY on the actual input/output content within each example
- The dataset format does NOT determine what output format the prompt expects
- Base your metrics on what the prompt asks for, not how the dataset is formatted

ANALYSIS REQUIREMENTS:
1. FIRST: Analyze what the prompt is asking the AI to do and what output format is expected
2. Examine the ACTUAL data content and field names (ignore storage format)
3. Create metrics that measure success for this specific task

CRITICAL: Start your analysis by clearly stating what you understand the prompt's intent to be.

Based on this analysis, suggest 2-3 simple evaluation metrics. For each metric, provide:

1. **Metric Name**: Clear, descriptive name
2. **Intent Understanding**: What the prompt is asking for and how this metric measures success
3. **Data Fields Used**: Exactly which fields from the dataset this metric will access
4. **Evaluation Logic**: Simple logic for comparing predicted vs expected values
5. **Example**: How it would evaluate a sample from this dataset

Focus on metrics that are:
- Simple and focused on the core task
- Use the exact field names from the dataset
- Measure what the prompt is actually asking for
- Avoid overfitting or complex scoring
- Independent of dataset storage format (JSONL, CSV, etc.)

Format your response as JSON:
{{
  "intent_analysis": "REQUIRED: Clear description of the task based on the dataset structure and expected output format. Focus on what evaluation metrics should measure based on the data patterns.",
  "metrics": [
    {{
      "name": "Metric Name",
      "intent_understanding": "How this metric measures success for the data classification task",
      "data_fields": ["field1", "field2"],
      "evaluation_logic": "Simple comparison logic using actual field names",
      "example": "Example using actual data structure"
    }}
  ],
  "reasoning": "Why these simple metrics effectively measure the data classification task (focus on data structure and evaluation requirements)"
}}"""
        """
        DATASET ANALYSIS PROMPT
        
        Purpose: Analyzes user datasets to automatically infer appropriate evaluation metrics
        Used in: /metrics page -> "Infer from Dataset" tab -> form submission
        Called by: app.py -> infer_metrics_from_dataset() -> get_dataset_analysis_prompt()
        API Call: Bedrock Nova (Premier/Pro/Lite) via call_ai_for_metric_inference()
        
        Input: Raw dataset content (JSON samples), focus areas (accuracy, format, etc.), analysis depth
        Output: JSON with suggested metrics, descriptions, criteria, and reasoning
        
        Flow: User selects dataset -> AI analyzes structure/content -> Suggests relevant metrics -> 
              Feeds into metric_code_generation() to create executable Python code
        """
        # Build detailed focus areas text with new granular options
        focus_mapping = {
            # Accuracy & Correctness
            'exact_match': 'exact string matching between predicted and expected outputs',
            'semantic_equiv': 'semantic equivalence even when wording differs',
            'factual_accuracy': 'factual correctness and truthfulness of information',
            'numerical_precision': 'accuracy of numerical values and calculations',
            'classification_accuracy': 'correct classification or categorization',
            
            # Format & Structure
            'valid_json': 'valid JSON, XML, or YAML format compliance',
            'required_fields': 'presence of all required fields or elements',
            'correct_types': 'correct data types for each field',
            'schema_compliance': 'adherence to predefined schemas or structures',
            'length_constraints': 'appropriate length limits and constraints',
            
            # Completeness
            'all_requirements': 'addressing all specified requirements',
            'sufficient_detail': 'providing adequate level of detail',
            'topic_coverage': 'comprehensive coverage of relevant topics',
            'edge_cases': 'handling of edge cases and exceptions',
            'context_preservation': 'maintaining important contextual information',
            
            # Relevance
            'query_alignment': 'alignment with the specific query or request',
            'context_awareness': 'understanding and using provided context',
            'topic_relevance': 'relevance to the main topic or subject',
            'intent_understanding': 'understanding user intent and purpose',
            'appropriate_scope': 'maintaining appropriate scope and boundaries'
        }
        
        if focus_areas:
            focus_descriptions = [focus_mapping.get(area, area) for area in focus_areas]
            focus_text = f"\nPay special attention to: {', '.join(focus_descriptions)}"
        else:
            focus_text = ""
        
        # Add prompt analysis if provided
        prompt_analysis_text = ""
        if prompt_content:
            prompt_analysis_text = f"""

ORIGINAL PROMPT ANALYSIS:
The following is the original prompt that will be used with this dataset:
---
{prompt_content}
---

CRITICAL PROMPT INTENT ANALYSIS:
1. Analyze the prompt's specific task and expected behavior
2. Identify what the prompt is asking the AI to do (classify, generate, transform, etc.)
3. Determine the expected output format based on the prompt instructions
4. Understand the success criteria implied by the prompt
5. Validate that the dataset examples align with the prompt's intended use case

The metrics MUST evaluate how well responses fulfill the prompt's specific requirements and intended behavior. Consider:
- Does the prompt ask for classification? → Metrics should measure classification accuracy
- Does the prompt ask for JSON output? → Metrics should validate JSON structure
- Does the prompt specify certain fields? → Metrics should check those exact fields
- Does the prompt have quality criteria? → Metrics should measure those criteria"""
        
        return f"""You are an expert in AI evaluation metrics. Analyze the following dataset and suggest appropriate evaluation metrics.

Dataset Content ({analysis_depth} analysis):
```
{dataset_content}
```

{focus_text}{prompt_analysis_text}

CRITICAL: Analyze the ACTUAL data structure in the dataset above. Look at:
- What fields are present in the data (e.g., "categories", "sentiment", "urgency", etc.)
- What data types are used (strings, numbers, booleans, objects)
- What the expected output format appears to be
- How the input and expected output relate to each other

{f"VALIDATE AGAINST ORIGINAL INTENT: Ensure the evaluation criteria aligns with the original prompt's task and expected behavior. The metrics must measure success for the specific tasks the prompt is designed to perform." if prompt_content else ""}

Based on this SPECIFIC dataset structure{" and original prompt intent" if prompt_content else ""}, suggest up to 10 evaluation metrics that work with the entire output. For each metric, provide:

1. **Metric Name**: Clear, descriptive name
2. **Description**: What it measures and why it's important for THIS specific data
3. **Data Fields Used**: Exactly which fields from the dataset this metric will access
4. **Evaluation Logic**: Specific logic for comparing predicted vs expected values using the actual field names
5. **Example**: How it would evaluate a sample from THIS dataset using the actual field structure

Focus on metrics that are:
- Specific to the ACTUAL data structure shown above
- Use the EXACT field names present in the dataset
- Handle the ACTUAL data types (strings, numbers, booleans, objects)
- Relevant for the apparent use case based on the data content

Format your response as JSON:
{{
  "metrics": [
    {{
      "name": "Metric Name",
      "description": "What this metric measures for this specific data",
      "data_fields": ["field1", "field2"],
      "evaluation_logic": "How to compare using actual field names",
      "example": "Example using actual data structure"
    }}
  ],
  "data_structure_analysis": "Analysis of the actual data structure and field types",
  "prompt_intent_validation": "How these metrics align with the original prompt's intended task and success criteria",
  "reasoning": "Why these metrics are appropriate for this specific dataset structure and prompt intent"
}}"""

    @staticmethod
    def metric_code_generation(name: str, criteria: dict) -> str:
        """
        METRIC CODE GENERATION PROMPT
        
        Purpose: Converts metric descriptions/criteria into executable Python MetricAdapter classes
        Used in: Multiple places where metrics need executable code
        Called by: 
          - metric_service.py -> generate_metric_code() (for inferred metrics)
          - Natural language metric creation
          - Manual metric code generation
        API Call: Bedrock Nova via MetricService.generate_metric_code()
        
        Input: Metric name, evaluation criteria (from dataset analysis or user input)
        Output: Complete Python class inheriting from MetricAdapter with apply() method
        
        Flow: Metric criteria -> AI generates Python code -> Code saved to database -> 
              Used by sdk_worker.py during optimization to score prompt candidates
        """
        
        return f"""Generate a Python MetricAdapter subclass for evaluating AI outputs.

Requirements:
- Metric Name: {name}
- Evaluation Criteria: {criteria.get('natural_language', '')}
- Dataset Format: {criteria.get('dataset_format', 'auto-detect')}

CRITICAL: ANALYZE THE ACTUAL DATA STRUCTURE FROM THESE EXAMPLES:
{criteria.get('metrics_description', 'No data samples provided')}

INSTRUCTIONS:
1. **Examine the data samples above** to understand the actual input/output format
2. **Determine the appropriate parsing method** based on what you see:
   - If data contains JSON objects, use JSON parsing
   - If data contains XML-like tags, use regex extraction
   - If data is plain text, use string operations
   - If data has other formats, adapt accordingly

3. **Implement appropriate parsing logic** for the format you identified

4. **Return detailed scoring structure**:
   - Individual metric scores (metric_1_score, metric_2_score, etc.)
   - Overall "total" score combining all metrics
   - Any validation flags if needed

5. **Handle errors gracefully** and return meaningful scores even when parsing fails

6. **Use the specific metrics described** in the evaluation criteria above

CRITICAL: Do NOT assume any specific format. Base your implementation entirely on the actual data samples shown above.

Required imports:
from amzn_nova_prompt_optimizer.core.input_adapters.metric_adapter import MetricAdapter
from typing import List, Any, Dict
import re

Add any additional imports (like json) only if needed based on the data format you identify.

Generate the complete class that properly handles the data format shown in the examples."""

    @staticmethod
    def natural_language_metric(name: str, description: str, natural_language: str, model_id: str) -> str:
        """Natural language metric creation prompt"""
        return f"""Create a Python MetricAdapter class for: {name}

Description: {description}
Evaluation Criteria: {natural_language}

Generate a complete Python class that properly handles the data format shown in the examples."""
    @staticmethod
    def get_composite_metric_prompt(metrics: list, weights: list = None, dataset_structure: dict = None, original_prompt: str = None) -> str:
        """Generate prompt for creating a composite metric from multiple metric descriptions"""
        
        if weights is None:
            weights = [1.0 / len(metrics)] * len(metrics)
        
        metrics_description = "\n".join([f"- {metric['name']}: {metric['description']}" for metric in metrics])
        weights_description = ", ".join([f"{metric['name']}: {weight}" for metric, weight in zip(metrics, weights)])
        
        return f"""Generate a Python composite metric that combines multiple evaluation metrics.

Metrics to combine:
{metrics_description}

Weights: {weights_description}

Dataset structure: {dataset_structure}

Generate a complete CompositeMetric class that inherits from MetricAdapter and combines all the specified metrics with the given weights.

Required imports:
from amzn_nova_prompt_optimizer.core.input_adapters.metric_adapter import MetricAdapter
from typing import List, Any, Dict
import re
import json

Return only the Python class code."""

    @staticmethod
    def natural_language_metric(name: str, description: str, natural_language: str, model_id: str) -> str:
        """Natural language metric creation prompt"""
        return f"""Create a Python MetricAdapter class for: {name}

Description: {description}
Evaluation Criteria: {natural_language}

Generate a complete Python class that inherits from MetricAdapter.
Return only the Python class code, no explanations."""
