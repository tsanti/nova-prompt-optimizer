#!/Users/tsanti/Development/Publish/nova-prompt-optimizer/.venv/bin/python3
"""
Nova Prompt Optimizer - SDK Proxy Worker
Uses the installed Nova SDK from .venv
"""

import json
import os
import sys
from pathlib import Path
from pathlib import Path

# Ensure we're in the frontend directory and use the same database
frontend_dir = Path(__file__).parent
os.chdir(frontend_dir)
sys.path.insert(0, str(frontend_dir))

from database import Database

# Nova model configurations (simplified to avoid pydantic dependency)
NOVA_MODELS = {
    "nova-micro": {"id": "us.amazon.nova-micro-v1:0", "max_tokens": 8192},
    "nova-lite": {"id": "us.amazon.nova-lite-v1:0", "max_tokens": 32768},
    "nova-pro": {"id": "us.amazon.nova-pro-v1:0", "max_tokens": 32768},
    "nova-premier": {"id": "us.amazon.nova-premier-v1:0", "max_tokens": 32768},
}


def clean_generated_code(raw_code: str) -> str:
    """Clean generated code by removing markdown formatting"""
    import re

    # Remove markdown code blocks
    code = re.sub(r"```python\s*\n?", "", raw_code)
    code = re.sub(r"```\s*$", "", code)
    code = re.sub(r"^```\s*\n?", "", code)

    # Remove any remaining markdown artifacts
    code = re.sub(r"^\s*```.*?\n", "", code, flags=re.MULTILINE)
    code = re.sub(r"\n\s*```\s*$", "", code)

    return code.strip()


# Import the installed SDK (not from /src)
from amzn_nova_prompt_optimizer.core.input_adapters.prompt_adapter import (
    TextPromptAdapter,
)
from amzn_nova_prompt_optimizer.core.input_adapters.dataset_adapter import (
    JSONDatasetAdapter,
)
from amzn_nova_prompt_optimizer.core.input_adapters.metric_adapter import MetricAdapter
from amzn_nova_prompt_optimizer.core.optimizers import NovaPromptOptimizer
from amzn_nova_prompt_optimizer.core.inference.adapter import BedrockInferenceAdapter
from amzn_nova_prompt_optimizer.core.evaluation import Evaluator


def run_optimization_worker(optimization_id: str, config: dict = None):
    """Run optimization using the real Nova SDK"""
    db = Database()

    try:
        # 1. Load optimization data
        optimization = db.get_optimization_by_id(optimization_id)
        if not optimization:
            print(f"❌ Optimization {optimization_id} not found")
            return

        # Use provided config or try to get from command line
        if config is None:
            try:
                config = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
            except (IndexError, json.JSONDecodeError):
                # Default config for thread calls
                config = {
                    "model_id": "us.amazon.nova-premier-v1:0",
                    "rate_limit": 60,
                    "mode": "pro",
                }

        db.add_optimization_log(
            optimization_id, "info", "🚀 Starting SDK-based optimization"
        )

        # 2. Load prompt data from database
        db.add_optimization_log(
            optimization_id, "debug", f"Looking for prompt ID: {optimization['prompt']}"
        )

        prompt_data = db.get_prompt(optimization["prompt"])
        db.add_optimization_log(
            optimization_id, "debug", f"Prompt data found: {prompt_data is not None}"
        )

        if not prompt_data:
            # List available prompts for debugging
            all_prompts = db.get_prompts()
            prompt_ids = [p["id"] for p in all_prompts]
            db.add_optimization_log(
                optimization_id, "debug", f"Available prompt IDs: {prompt_ids}"
            )
            raise Exception(f"Prompt data not found for ID: {optimization['prompt']}")

        # Parse the variables field to get system and user prompts
        variables_data = prompt_data["variables"]

        # Handle both old format (array) and new format (object with prompts)
        if isinstance(variables_data, dict) and "system_prompt" in variables_data:
            # New format: variables contains actual prompts
            system_prompt = variables_data.get("system_prompt", "")
            user_prompt = variables_data.get("user_prompt", "Analyze: {input}")
        else:
            # Old format: variables is array of variable names, prompts not stored
            system_prompt = ""
            user_prompt = "Analyze: {input}"
            db.add_optimization_log(
                optimization_id,
                "warning",
                "Using old prompt format, prompts may be empty",
            )

        # DEBUG: Check prompt content
        print(f"🔍 DEBUG - Variables data: {variables_data}")
        print(
            f"🔍 DEBUG - System prompt: '{system_prompt[:100]}...' (length: {len(system_prompt)})"
        )
        print(f"🔍 DEBUG - User prompt: '{user_prompt}' (length: {len(user_prompt)})")

        db.add_optimization_log(
            optimization_id, "debug", f"System prompt length: {len(system_prompt)}"
        )
        db.add_optimization_log(
            optimization_id, "debug", f"User prompt length: {len(user_prompt)}"
        )

        # Ensure we have a valid user prompt
        if not user_prompt or user_prompt.strip() == "":
            user_prompt = "Analyze the following input: {input}"
            db.add_optimization_log(
                optimization_id, "warning", "Empty user prompt detected, using default"
            )

        # 3. Create prompt adapter using real SDK (match notebook pattern)
        prompt_variables = {"input"}  # Variables used in prompts
        prompt_adapter = TextPromptAdapter()

        if system_prompt:
            prompt_adapter.set_system_prompt(
                content=system_prompt, variables=prompt_variables
            )
        prompt_adapter.set_user_prompt(content=user_prompt, variables=prompt_variables)
        prompt_adapter.adapt()

        db.add_optimization_log(optimization_id, "success", "✅ Prompt adapter created")

        # 4. Load dataset from database
        dataset_data = db.get_dataset(optimization["dataset"])
        if not dataset_data:
            raise Exception("Dataset not found")

        dataset_content = dataset_data["content"]
        db.add_optimization_log(
            optimization_id, "debug", f"Dataset content length: {len(dataset_content)}"
        )
        db.add_optimization_log(
            optimization_id,
            "debug",
            f"Dataset content preview: {dataset_content[:200]}...",
        )

        # Write dataset to temp file for SDK
        temp_dataset_path = f"data/temp_dataset_{optimization_id}.jsonl"
        with open(temp_dataset_path, "w") as f:
            f.write(dataset_content)

        db.add_optimization_log(
            optimization_id, "debug", f"Created temp file: {temp_dataset_path}"
        )

        # Verify file exists and has content
        import os

        if not os.path.exists(temp_dataset_path):
            raise Exception(f"Temp dataset file not created: {temp_dataset_path}")

        file_size = os.path.getsize(temp_dataset_path)
        db.add_optimization_log(
            optimization_id, "debug", f"Temp file size: {file_size} bytes"
        )

        # Smart field detection - find the output field automatically
        output_field = None
        if dataset_content.strip():
            try:
                # Parse first line to detect fields
                first_line = dataset_content.strip().split("\n")[0]
                sample_record = json.loads(first_line)

                # Common output field names in order of preference
                possible_output_fields = [
                    "answer",
                    "output",
                    "response",
                    "result",
                    "label",
                    "target",
                    "ground_truth",
                ]

                for field in possible_output_fields:
                    if field in sample_record:
                        output_field = field
                        break

                # If none found, use the second field (assuming first is input)
                if not output_field:
                    fields = list(sample_record.keys())
                    if len(fields) >= 2:
                        output_field = fields[1]  # Second field as output

                db.add_optimization_log(
                    optimization_id,
                    "info",
                    f"🔍 Detected output field: '{output_field}'",
                )

            except Exception as e:
                db.add_optimization_log(
                    optimization_id, "warning", f"⚠️ Could not detect output field: {e}"
                )
                output_field = "answer"  # Default fallback

        if not output_field:
            output_field = "answer"  # Final fallback

        # Create dataset adapter with detected fields
        dataset_adapter = JSONDatasetAdapter({"input"}, {output_field})

        try:
            dataset_adapter.adapt(data_source=temp_dataset_path)

            # Apply record limit if specified
            record_limit = config.get("record_limit")
            if record_limit and record_limit > 0:
                original_size = len(dataset_adapter.standardized_dataset)
                dataset_adapter.standardized_dataset = (
                    dataset_adapter.standardized_dataset[:record_limit]
                )
                db.add_optimization_log(
                    optimization_id,
                    "info",
                    f"📊 Dataset limited from {original_size} to {len(dataset_adapter.standardized_dataset)} samples",
                )

            db.add_optimization_log(
                optimization_id,
                "debug",
                f"Dataset adapted successfully: {len(dataset_adapter.standardized_dataset)} samples",
            )
        except Exception as e:
            db.add_optimization_log(
                optimization_id, "error", f"Dataset adapt failed: {e}"
            )
            raise Exception(f"Dataset adaptation failed: {e}")

        train_dataset, test_dataset = dataset_adapter.split(
            config.get("train_split", 0.5)
        )  # Use configurable split

        db.add_optimization_log(
            optimization_id,
            "debug",
            f"Train dataset size: {len(train_dataset.standardized_dataset) if hasattr(train_dataset, 'standardized_dataset') else 'unknown'} (split: {config.get('train_split', 0.5):.0%})",
        )
        db.add_optimization_log(
            optimization_id,
            "debug",
            f"Test dataset size: {len(test_dataset.standardized_dataset) if hasattr(test_dataset, 'standardized_dataset') else 'unknown'} (split: {1 - config.get('train_split', 0.5):.0%})",
        )

        # DEBUG: Check test dataset content
        if (
            hasattr(test_dataset, "standardized_dataset")
            and test_dataset.standardized_dataset
        ):
            first_test_sample = test_dataset.standardized_dataset[0]
            print(f"🔍 DEBUG - First test sample: {first_test_sample}")
            print(
                f"🔍 DEBUG - Test sample keys: {list(first_test_sample.keys()) if isinstance(first_test_sample, dict) else 'not dict'}"
            )

            # Check if input field exists and has content
            input_content = (
                first_test_sample.get("input", "")
                if isinstance(first_test_sample, dict)
                else ""
            )
            print(
                f"🔍 DEBUG - Input content: '{input_content}' (length: {len(str(input_content))})"
            )

            db.add_optimization_log(
                optimization_id,
                "debug",
                f"First test sample keys: {list(first_test_sample.keys()) if isinstance(first_test_sample, dict) else 'not dict'}",
            )
            db.add_optimization_log(
                optimization_id,
                "debug",
                f"Input content length: {len(str(input_content))}",
            )
        else:
            print("🔍 DEBUG - Test dataset is empty or malformed")
            db.add_optimization_log(
                optimization_id, "error", "❌ Test dataset is empty or malformed"
            )

        if (
            not hasattr(train_dataset, "standardized_dataset")
            or len(train_dataset.standardized_dataset) == 0
        ):
            db.add_optimization_log(
                optimization_id,
                "error",
                f"❌ Training dataset is empty. Original dataset size: {len(dataset_adapter.standardized_dataset) if hasattr(dataset_adapter, 'standardized_dataset') else 'unknown'}",
            )
            db.add_optimization_log(
                optimization_id,
                "error",
                f"❌ Dataset content was: {dataset_content[:500]}...",
            )
            raise Exception("Training dataset is empty after split")

        # Ensure minimum dataset size for MIPROv2
        if len(train_dataset.standardized_dataset) < 2:
            db.add_optimization_log(
                optimization_id,
                "error",
                f"❌ Training dataset too small: {len(train_dataset.standardized_dataset)} samples. Need at least 2.",
            )
            raise Exception(
                f"Training dataset too small: {len(train_dataset.standardized_dataset)} samples. MIPROv2 needs at least 2 training samples."
            )

        db.add_optimization_log(
            optimization_id,
            "success",
            f"✅ Dataset loaded: {len(dataset_adapter.standardized_dataset)} samples",
        )

        # 5. Load custom metric from database
        print("🔍 DEBUG - STARTING METRIC LOADING SECTION")
        print(f"🔍 DEBUG - Optimization ID: {optimization_id}")

        optimization_data = db.get_optimization_by_id(optimization_id)
        print(f"🔍 DEBUG - Optimization data: {optimization_data}")
        print(f"🔍 DEBUG - Optimization data type: {type(optimization_data)}")

        metric_id = optimization_data.get("metric_id") if optimization_data else None
        print(f"🔍 DEBUG - Extracted metric_id: {metric_id}")
        print(f"🔍 DEBUG - Metric_id type: {type(metric_id)}")

        if metric_id:
            print(f"🔍 DEBUG - Loading custom metric: {metric_id}")
            custom_metric = db.get_metric_by_id(metric_id)
            if custom_metric:
                print(f"🔍 DEBUG - Custom metric found: {custom_metric['name']}")
                print(
                    f"🔍 DEBUG - Generated code length: {len(custom_metric['generated_code'])} chars"
                )

                # Create dynamic metric class with custom code
                class CustomMetricAdapter(MetricAdapter):
                    def parse_metric_input(self, data):
                        """
                        Flexible parser for metric inputs that can handle various formats
                        from AI-generated metrics, including markdown code blocks
                        """
                        if data is None:
                            return None

                        # Already parsed object
                        if isinstance(data, (dict, list, int, float, bool)):
                            return data

                        # String that needs parsing
                        if isinstance(data, str):
                            data = data.strip()

                            # First, try to extract content from markdown code blocks
                            import re

                            extracted_content = data

                            # Check for any markdown code blocks and extract the content
                            code_block_patterns = [
                                re.compile(
                                    r"```(?:json|xml|yaml|yml|text|plain)?\s*(.*?)\s*```",
                                    re.DOTALL | re.IGNORECASE,
                                ),
                                re.compile(r"```(.*?)```", re.DOTALL),
                            ]

                            for pattern in code_block_patterns:
                                match = pattern.search(data)
                                if match:
                                    extracted_content = match.group(1).strip()
                                    print(
                                        f"🔍 DEBUG - Found markdown code block, extracted: {extracted_content[:100]}..."
                                    )
                                    print(
                                        f"🔍 DEBUG - Original had markdown wrapper: {data[:50]}...{data[-50:]}"
                                    )
                                    break

                            # Try JSON parsing on the extracted content
                            try:
                                return json.loads(extracted_content)
                            except json.JSONDecodeError:
                                pass

                            # Try eval for Python literals (safe subset) on extracted content
                            try:
                                import ast

                                return ast.literal_eval(extracted_content)
                            except:
                                pass

                            # Try parsing as number on extracted content
                            try:
                                if "." in extracted_content:
                                    return float(extracted_content)
                                else:
                                    return int(extracted_content)
                            except:
                                pass

                            # Try parsing boolean on extracted content
                            if extracted_content.lower() in ("true", "false"):
                                return extracted_content.lower() == "true"

                            # Try parsing None on extracted content
                            if extracted_content.lower() in ("none", "null"):
                                return None

                            # Return extracted content as string if all else fails
                            return extracted_content

                        # Return as-is for other types
                        return data

                    def apply(self, y_pred, y_true):
                        try:
                            print(
                                f"🔍 DEBUG - Custom metric input: y_pred={str(y_pred)[:100]}..., y_true={str(y_true)[:100]}..."
                            )

                            # INTEGRITY CHECKS - Verify actual data vs display truncation
                            print(
                                f"🔍 INTEGRITY - y_pred type: {type(y_pred)}, length: {len(str(y_pred))}"
                            )
                            print(
                                f"🔍 INTEGRITY - y_true type: {type(y_true)}, length: {len(str(y_true))}"
                            )
                            print(
                                f"🔍 INTEGRITY - y_pred ends with: '{str(y_pred)[-50:] if len(str(y_pred)) > 50 else str(y_pred)}'"
                            )
                            print(
                                f"🔍 INTEGRITY - y_true ends with: '{str(y_true)[-50:] if len(str(y_true)) > 50 else str(y_true)}'"
                            )
                            print(
                                f"🔍 INTEGRITY - y_pred is complete JSON: {str(y_pred).strip().endswith('}') if isinstance(y_pred, str) else 'N/A'}"
                            )
                            print(
                                f"🔍 INTEGRITY - y_true is complete JSON: {str(y_true).strip().endswith('}') if isinstance(y_true, str) else 'N/A'}"
                            )

                            # Execute the generated metric code to define the class
                            local_vars = {}

                            # Define a robust content parser function for generated metrics
                            def robust_content_parse(
                                input_string: str, target_format="json"
                            ):
                                """Robust content parser that handles markdown code blocks for any format"""
                                import json
                                import re

                                if not isinstance(input_string, str):
                                    return input_string

                                # First, try to extract content from markdown code blocks
                                extracted_content = input_string.strip()

                                # Check for any markdown code blocks and extract the content
                                code_block_patterns = [
                                    re.compile(
                                        r"```(?:json|xml|yaml|yml|text|plain)?\s*(.*?)\s*```",
                                        re.DOTALL | re.IGNORECASE,
                                    ),
                                    re.compile(r"```(.*?)```", re.DOTALL),
                                ]

                                for pattern in code_block_patterns:
                                    match = pattern.search(input_string)
                                    if match:
                                        extracted_content = match.group(1).strip()
                                        break

                                # Try parsing based on target format
                                if target_format.lower() == "json":
                                    try:
                                        return json.loads(extracted_content)
                                    except json.JSONDecodeError as err:
                                        # If JSON parsing fails, return the extracted content as string
                                        return extracted_content
                                else:
                                    # For non-JSON formats, return the extracted content
                                    return extracted_content

                            # Backward compatibility alias
                            def robust_json_parse(input_string: str):
                                return robust_content_parse(input_string, "json")

                            global_vars = {
                                "MetricAdapter": MetricAdapter,
                                "json": __import__("json"),
                                "re": __import__("re"),
                                "math": __import__("math"),
                                "Any": __import__("typing").Any,
                                "List": __import__("typing").List,
                                "Dict": __import__("typing").Dict,
                                "robust_json_parse": robust_json_parse,
                                "robust_content_parse": robust_content_parse,
                            }

                            # Clean the code before execution
                            cleaned_code = clean_generated_code(
                                custom_metric["generated_code"]
                            )

                            # Show code only once at the beginning
                            if not hasattr(self, "_code_shown"):
                                print(f"🔍 DEBUG - Executing metric code:")
                                print(f"```python\n{cleaned_code}\n```")
                                self._code_shown = True

                            exec(cleaned_code, global_vars, local_vars)

                            # Find the metric class in the executed code
                            metric_class = None
                            for name, obj in local_vars.items():
                                if isinstance(obj, type) and name not in [
                                    "json",
                                    "re",
                                    "math",
                                    "Any",
                                    "List",
                                    "Dict",
                                    "MetricAdapter",
                                ]:
                                    if hasattr(obj, "apply") and hasattr(
                                        obj, "batch_apply"
                                    ):
                                        metric_class = obj
                                        break

                            if metric_class:
                                print(
                                    f"🔍 DEBUG - Found metric class: {metric_class.__name__}"
                                )
                                # Instantiate and use the metric
                                metric_instance = metric_class()

                                # Use flexible parsing for inputs
                                parsed_y_pred = self.parse_metric_input(y_pred)
                                parsed_y_true = self.parse_metric_input(y_true)

                                print(
                                    f"🔍 DEBUG - Parsed inputs: y_pred={type(parsed_y_pred)} {str(parsed_y_pred)[:100]}"
                                )
                                print(
                                    f"🔍 DEBUG - Parsed inputs: y_true={type(parsed_y_true)} {str(parsed_y_true)[:100]}"
                                )

                                # Add safety wrapper for metric execution
                                try:
                                    result = metric_instance.apply(
                                        parsed_y_pred, parsed_y_true
                                    )
                                except (
                                    TypeError,
                                    KeyError,
                                    AttributeError,
                                    ValueError,
                                ) as e:
                                    print(
                                        f"⚠️ DEBUG - Metric data structure mismatch: {e}"
                                    )
                                    print(
                                        f"⚠️ DEBUG - Expected fields not found in data structure"
                                    )
                                    # Try simple comparison fallback
                                    if parsed_y_pred == parsed_y_true:
                                        result = 1.0
                                    else:
                                        # Calculate basic similarity for dict structures
                                        if isinstance(
                                            parsed_y_pred, dict
                                        ) and isinstance(parsed_y_true, dict):
                                            pred_keys = set(
                                                str(k) + str(v)
                                                for k, v in parsed_y_pred.items()
                                                if isinstance(
                                                    v, (str, int, float, bool)
                                                )
                                            )
                                            true_keys = set(
                                                str(k) + str(v)
                                                for k, v in parsed_y_true.items()
                                                if isinstance(
                                                    v, (str, int, float, bool)
                                                )
                                            )
                                            if pred_keys or true_keys:
                                                result = len(
                                                    pred_keys & true_keys
                                                ) / max(len(pred_keys | true_keys), 1)
                                            else:
                                                result = 0.5  # Neutral score for complex structures
                                        else:
                                            result = 0.0
                                    print(
                                        f"🔄 DEBUG - Using fallback similarity score: {result}"
                                    )

                                result = result

                                # Ensure result is a valid float between 0-1
                                # Handle Dict returns (detailed metrics)
                                if isinstance(result, dict):
                                    if "total" in result:
                                        result = float(result["total"])
                                        print(
                                            f"✅ DEBUG - Extracted total score from dict: {result}"
                                        )
                                    else:
                                        print(
                                            "⚠️ DEBUG - Dict result has no 'total' field, using 0.0"
                                        )
                                        return 0.0
                                elif result is None:
                                    print("⚠️ DEBUG - Metric returned None, using 0.0")
                                    return 0.0
                                else:
                                    result = float(result)

                                # Handle scale conversion - composite metrics typically use 0-4 scale
                                if result > 1.0:
                                    print(
                                        f"⚠️ DEBUG - Metric returned {result} > 1.0, assuming 0-4 scale, converting to 0-1"
                                    )
                                    result = result / 4.0  # Convert from 0-4 scale to 0-1 scale

                                # Clamp to 0-1 range
                                result = max(0.0, min(1.0, result))

                                print(f"✅ DEBUG - Custom metric final score: {result}")
                                return result
                            else:
                                print(
                                    "❌ DEBUG - No MetricAdapter subclass found in generated code"
                                )
                                return 0.0

                        except Exception as e:
                            print(f"❌ DEBUG - Custom metric execution failed: {e}")
                            print(
                                f"🔍 DEBUG - Failed y_pred: '{y_pred}' (type: {type(y_pred)}, len: {len(str(y_pred)) if y_pred else 0})"
                            )
                            print(
                                f"🔍 DEBUG - Failed y_true: '{y_true}' (type: {type(y_true)}, len: {len(str(y_true)) if y_true else 0})"
                            )
                            import traceback

                            print(f"❌ DEBUG - Traceback: {traceback.format_exc()}")
                            print("🔄 DEBUG - Falling back to default scoring")
                            return 0.0

                    def batch_apply(self, y_preds, y_trues):
                        # Calculate average of individual scores for custom metric
                        scores = [
                            self.apply(pred, true)
                            for pred, true in zip(y_preds, y_trues)
                        ]
                        return sum(scores) / len(scores) if scores else 0.0

                metric_adapter = CustomMetricAdapter()
                db.add_optimization_log(
                    optimization_id,
                    "success",
                    f"✅ Custom metric loaded: {custom_metric['name']}",
                )
            else:
                print(f"❌ DEBUG - Custom metric not found: {metric_id}")

                # Fallback to default metric
                class AnalyzerMetric(MetricAdapter):
                    def apply(self, y_pred, y_true):
                        return 1.0  # Default score

                    def batch_apply(self, y_preds, y_trues):
                        # Calculate average of individual scores for fallback metric
                        scores = [
                            self.apply(pred, true)
                            for pred, true in zip(y_preds, y_trues)
                        ]
                        return sum(scores) / len(scores) if scores else 0.0

                metric_adapter = AnalyzerMetric()
        else:
            print("🔍 DEBUG - No custom metric specified, using default")

            # Default metric adapter (original hardcoded logic)
            class AnalyzerMetric(MetricAdapter):
                def apply(self, y_pred, y_true):
                    try:
                        import json
                        import re

                        # Parse JSON from prediction
                        json_match = re.search(r"\{.*\}", str(y_pred), re.DOTALL)
                        if not json_match:
                            return 0.0

                        pred_json = json.loads(json_match.group())
                        true_json = (
                            json.loads(y_true) if isinstance(y_true, str) else y_true
                        )

                        score = 0.0
                        total = 0

                        for field in ["urgency", "sentiment", "categories"]:
                            if field in true_json:
                                total += 1
                                if (
                                    field in pred_json
                                    and pred_json[field] == true_json[field]
                                ):
                                    score += 1.0

                        return score / total if total > 0 else 0.0
                    except:
                        return 0.0

                def batch_apply(self, y_preds, y_trues):
                    # Calculate average of individual scores for generated metric
                    scores = [
                        self.apply(pred, true) for pred, true in zip(y_preds, y_trues)
                    ]
                    return sum(scores) / len(scores) if scores else 0.0

            metric_adapter = AnalyzerMetric()

        # 6. Create inference adapter with dynamic rate limit allocation
        rate_limit_value = config.get("rate_limit", 2)
        # 6. Create inference adapter with full rate limit allocation to backend
        rate_limit_value = config.get(
            "rate_limit", 2
        )  # Give full rate limit to Nova SDK
        print(
            f"🔍 DEBUG - Full rate limit allocation to Nova SDK: {rate_limit_value} RPM"
        )

        # Create inference adapter - Nova SDK will use this rate limit for all its connections
        inference_adapter = BedrockInferenceAdapter(
            region_name="us-east-1", rate_limit=rate_limit_value
        )

        # DEBUG: Check if SDK has any default inference parameters
        print(f"🔍 SDK CONFIG - Inference adapter created: {type(inference_adapter)}")
        if hasattr(inference_adapter, "inference_config"):
            print(
                f"🔍 SDK CONFIG - SDK inference config: {inference_adapter.inference_config}"
            )
        if hasattr(inference_adapter, "default_inference_config"):
            print(
                f"🔍 SDK CONFIG - SDK default config: {inference_adapter.default_inference_config}"
            )

        # Store backend rate limit as RPS (backend rate limiter expects requests per second)
        backend_rate_limit_rps = (
            rate_limit_value / 60.0
        )  # Convert RPM to RPS for backend

        # ELIMINATED: PromptCapturingAdapter wrapper
        # Nova SDK ignores our inference_adapter and creates its own DSPy LM instances
        # We'll capture optimization data through other means (database monitoring)

        # Wrap metric adapter to capture scores directly
        class ScoreCapturingMetric:
            def __init__(self, base_metric, optimization_id, db):
                self.base_metric = base_metric
                self.optimization_id = optimization_id
                self.db = db
                self.all_scores = []  # Track all scores for averaging
                self.score_count = 0
                self.all_scores = []  # Track all scores for averaging
                self.current_eval_scores = []  # Track scores for current evaluation round

            def apply(self, y_pred, y_true):
                score = self.base_metric.apply(y_pred, y_true)
                self.all_scores.append(score)

                # Calculate running average
                avg_score = sum(self.all_scores) / len(self.all_scores)

                print(
                    f"🎯 CAPTURED SCORE {len(self.all_scores)}: {score} (running avg: {avg_score:.3f})"
                )

                return score

            def get_average_score(self):
                """Get the average of all scores captured so far"""
                if self.all_scores:
                    return sum(self.all_scores) / len(self.all_scores)
                return 0.0

            def __getattr__(self, name):
                return getattr(self.base_metric, name)

        # Store original metric before wrapping to avoid infinite loop issues
        original_metric = metric_adapter
        metric_adapter = ScoreCapturingMetric(metric_adapter, optimization_id, db)

        db.add_optimization_log(optimization_id, "success", "✅ All adapters created")

        # 7. Run optimization using real SDK
        db.update_optimization_status(optimization_id, "Running", 50)

        nova_optimizer = NovaPromptOptimizer(
            prompt_adapter=prompt_adapter,
            inference_adapter=inference_adapter,  # Use the same rate-limited adapter
            dataset_adapter=train_dataset,
            metric_adapter=metric_adapter,
        )

        # Map model_id to model_mode if model_mode not provided
        model_mode = config.get("model_mode")
        if not model_mode:
            model_id = config.get("model_id", "us.amazon.nova-lite-v1:0")
            # Extract mode from model_id (e.g., "us.amazon.nova-pro-v1:0" -> "pro")
            if "nova-lite" in model_id:
                model_mode = "lite"
            elif "nova-pro" in model_id:
                model_mode = "pro"
            elif "nova-micro" in model_id:
                model_mode = "micro"
            elif "nova-premier" in model_id:
                model_mode = "premier"
            else:
                model_mode = "lite"  # fallback
        
        rate_limit = config.get("rate_limit", 2)

        # ATTEMPT: Set maximum possible tokens for the model
        model_max_tokens = NOVA_MODELS[f"nova-{model_mode}"]["max_tokens"]
        print(f"🔍 MAX_TOKENS - Setting maximum tokens to: {model_max_tokens}")

        # Try to set inference configuration if possible
        if hasattr(inference_adapter, "inference_config"):
            inference_adapter.inference_config = {"maxTokens": model_max_tokens}
            print(
                f"🔍 MAX_TOKENS - Set inference_config.maxTokens = {model_max_tokens}"
            )
        elif hasattr(inference_adapter, "default_inference_config"):
            inference_adapter.default_inference_config = {"maxTokens": model_max_tokens}
            print(
                f"🔍 MAX_TOKENS - Set default_inference_config.maxTokens = {model_max_tokens}"
            )
        else:
            print(f"🔍 MAX_TOKENS - No inference config attribute found on adapter")

        # DEBUG: Validate model and rate limit
        model_id = NOVA_MODELS[f"nova-{model_mode}"]["id"]
        print(f"🔍 DEBUG - Model mode: {model_mode}")
        print(f"🔍 DEBUG - Rate limit: {rate_limit} RPM")
        print(f"🔍 DEBUG - Model ID: {model_id}")
        print(
            f"🔍 DEBUG - Train/Test split: {config.get('train_split', 0.5):.0%}/{1 - config.get('train_split', 0.5):.0%}"
        )

        db.add_optimization_log(optimization_id, "info", f"🔄 Starting optimization...")
        db.add_optimization_log(
            optimization_id,
            "info",
            f"📋 Model: {model_mode} ({NOVA_MODELS[f'nova-{model_mode}']['id']})",
        )
        db.add_optimization_log(
            optimization_id,
            "info",
            f"📊 Train/Test Split: {config.get('train_split', 0.5):.0%}/{1 - config.get('train_split', 0.5):.0%}",
        )
        db.add_optimization_log(
            optimization_id,
            "info",
            f"⚡ Dynamic Rate Limiter - Shared pool: {rate_limit_value} RPM",
        )
        if rate_limit_value <= 6:
            db.add_optimization_log(
                optimization_id,
                "info",
                f"📊 Low rate limit detected - shared pool will be managed dynamically",
            )
        else:
            db.add_optimization_log(
                optimization_id,
                "info",
                f"📊 Frontend needs minimal RPM for batched evaluation, Backend gets majority",
            )
        db.add_optimization_log(
            optimization_id, "info", f"🔧 Initializing Nova Optimizer..."
        )

        # Create Nova optimizer with JSON fallback enabled
        nova_optimizer = NovaPromptOptimizer(
            prompt_adapter=prompt_adapter,
            inference_adapter=inference_adapter,  # Use the same rate-limited adapter
            dataset_adapter=train_dataset,
            metric_adapter=metric_adapter,
        )

        db.add_optimization_log(
            optimization_id,
            "info",
            f"🚀 Running optimization with Nova {model_mode.title()}...",
        )

        # Enable JSON fallback to avoid structured output issues
        print(f"🔍 DEBUG - About to call nova_optimizer.optimize(mode='{model_mode}')")
        optimized_prompt_adapter = nova_optimizer.optimize(mode=model_mode)

        db.add_optimization_log(
            optimization_id, "success", "✅ Optimization completed!"
        )

        # Calculate optimized score using official SDK Evaluator (CORRECTED APPROACH)
        try:
            # Use official SDK Evaluator for optimized prompt evaluation
            from amzn_nova_prompt_optimizer.core.evaluation import Evaluator

            print(
                f"🔍 DEBUG - Using official SDK Evaluator for optimized score calculation"
            )

            optimized_evaluator = Evaluator(
                optimized_prompt_adapter,
                test_dataset,
                original_metric,
                inference_adapter,
            )
            model_id = NOVA_MODELS[f"nova-{model_mode}"]["id"]
            optimized_score = optimized_evaluator.aggregate_score(model_id=model_id)

            print(f"🔍 DEBUG - Optimized score from Evaluator: {optimized_score}")
            db.add_optimization_log(
                optimization_id,
                "info",
                f"📊 Official SDK optimized score: {optimized_score}",
            )

            # Ensure we have a valid numeric score
            if optimized_score is None or not isinstance(optimized_score, (int, float)):
                print(f"🔍 DEBUG - Invalid optimized score, trying fallback")
                # Fallback to captured scores if available
                if hasattr(metric_adapter, "get_average_score"):
                    optimized_score = metric_adapter.get_average_score()
                    print(f"🔍 DEBUG - Fallback score: {optimized_score}")
                    db.add_optimization_log(
                        optimization_id,
                        "info",
                        f"📊 Using captured average score: {optimized_score:.3f}",
                    )
                else:
                    optimized_score = 0.0
                    print(f"🔍 DEBUG - No fallback available, using 0.0")

        except Exception as e:
            print(f"🔍 DEBUG - Exception in optimized score calculation: {e}")
            db.add_optimization_log(
                optimization_id,
                "warning",
                f"⚠️ Could not calculate optimized score: {e}",
            )
            # Fallback to captured scores if available
            if hasattr(metric_adapter, "get_average_score"):
                optimized_score = metric_adapter.get_average_score()
                db.add_optimization_log(
                    optimization_id,
                    "info",
                    f"📊 Using captured average score: {optimized_score:.3f}",
                )
            else:
                optimized_score = 0.0

        # Save prompt candidates to database
        try:
            print("🔍 DEBUG - Starting prompt candidate extraction...")

            # The PromptCapturingAdapter should have captured prompts during optimization
            # But let's also try to extract from the optimized prompt adapter directly
            candidates = []

            # Debug: Check what attributes are available
            print(
                f"🔍 DEBUG - Optimized adapter type: {type(optimized_prompt_adapter)}"
            )
            print(
                f"🔍 DEBUG - Available attributes: {[attr for attr in dir(optimized_prompt_adapter) if not attr.startswith('_')]}"
            )

            # Try to get the final optimized prompts
            try:
                final_system = getattr(optimized_prompt_adapter, "system_prompt", None)
                final_user = getattr(optimized_prompt_adapter, "user_prompt", None)
                few_shot_examples = getattr(
                    optimized_prompt_adapter, "few_shot_examples", []
                )

                print(
                    f"🔍 DEBUG - Extracted system_prompt: {bool(final_system)} ({len(str(final_system)) if final_system else 0} chars)"
                )
                print(
                    f"🔍 DEBUG - Extracted user_prompt: {bool(final_user)} ({len(str(final_user)) if final_user else 0} chars)"
                )
                print(
                    f"🔍 DEBUG - Extracted few_shot_examples: {len(few_shot_examples)} examples"
                )

                # Use optimized_score if available, otherwise default to 0.0
                score_to_use = (
                    optimized_score
                    if "optimized_score" in locals() and optimized_score is not None
                    else 0.0
                )

                if final_system and final_system.strip():
                    candidates.append(
                        {
                            "optimization_id": optimization_id,
                            "candidate_number": len(candidates) + 1,
                            "prompt_text": f"SYSTEM: {final_system[:500]}",
                            "score": score_to_use,
                        }
                    )
                    print(f"✅ DEBUG - Added system prompt candidate")

                if final_user and final_user.strip():
                    candidates.append(
                        {
                            "optimization_id": optimization_id,
                            "candidate_number": len(candidates) + 1,
                            "prompt_text": f"USER: {final_user[:500]}",
                            "score": score_to_use,
                        }
                    )
                    print(f"✅ DEBUG - Added user prompt candidate")

                # Add few-shot examples as candidates
                for i, example in enumerate(few_shot_examples[:3]):  # First 3 examples
                    candidates.append(
                        {
                            "optimization_id": optimization_id,
                            "candidate_number": len(candidates) + 1,
                            "prompt_text": f"FEW-SHOT {i + 1}: {str(example)[:300]}",
                            "score": score_to_use,
                        }
                    )
                    print(f"✅ DEBUG - Added few-shot example {i + 1}")

                print(f"🔍 DEBUG - Total candidates extracted: {len(candidates)}")

            except Exception as e:
                print(f"❌ DEBUG - Error extracting from optimized adapter: {e}")
                import traceback

                print(f"❌ DEBUG - Extraction traceback: {traceback.format_exc()}")

            # If we have candidates, save them
            if candidates:
                print(f"🔍 DEBUG - Saving {len(candidates)} candidates to database...")
                db.save_prompt_candidates(optimization_id, candidates)
                print(
                    f"✅ DEBUG - Successfully saved {len(candidates)} prompt candidates"
                )
            else:
                print("⚠️ DEBUG - No prompt candidates to save - adding fallback")
                # Add a fallback candidate so we don't show empty
                fallback_candidates = [
                    {
                        "optimization_id": optimization_id,
                        "candidate_number": 1,
                        "prompt_text": f"Optimization completed but prompt extraction failed. Check logs for details.",
                        "score": 0.0,
                    }
                ]
                db.save_prompt_candidates(optimization_id, fallback_candidates)
                print("✅ DEBUG - Added fallback candidate")

        except Exception as e:
            print(f"❌ DEBUG - Error in prompt candidate extraction: {e}")
            import traceback

            print(f"❌ DEBUG - Full traceback: {traceback.format_exc()}")
            db.add_optimization_log(
                optimization_id,
                "warning",
                f"⚠️ Could not save prompt candidates: {str(e)}",
            )

        db.add_optimization_log(optimization_id, "info", "📊 Starting evaluation...")

        # Update progress
        db.update_optimization_status(optimization_id, "Running", 80)

        # Import batched evaluator
        # 8. Baseline evaluation using SDK Evaluator (matches notebook pattern)
        db.update_optimization_status(optimization_id, "Running", 80)
        db.add_optimization_log(
            optimization_id,
            "info",
            "🔍 Evaluating baseline prompt using SDK Evaluator...",
        )

        try:
            # Create baseline evaluator using SDK pattern
            print(f"🔍 DEBUG - About to create baseline evaluator")
            print(f"🔍 DEBUG - test_dataset type: {type(test_dataset)}")

            # Fix: Create a completely new flattened dataset for baseline evaluation
            # The SDK expects {'input': '...', 'answer': '...'} but we have nested structure
            if (
                hasattr(test_dataset, "standardized_dataset")
                and test_dataset.standardized_dataset
            ):
                print(
                    f"🔍 DEBUG - Original test sample structure: {test_dataset.standardized_dataset[0]}"
                )

                # Create flattened JSONL file for baseline evaluation
                import tempfile

                flattened_data = []
                for sample in test_dataset.standardized_dataset:
                    # Handle different output key names (answer, output, etc.)
                    output_key = None
                    if "answer" in sample["outputs"]:
                        output_key = "answer"
                    elif "output" in sample["outputs"]:
                        output_key = "output"
                    else:
                        # Use the first available key
                        output_key = list(sample["outputs"].keys())[0]
                    
                    flattened_sample = {
                        "input": sample["inputs"]["input"],
                        "answer": sample["outputs"][output_key],
                    }
                    flattened_data.append(flattened_sample)

                print(f"🔍 DEBUG - Flattened test sample: {flattened_data[0]}")

                # Write flattened data to temporary file
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".jsonl", delete=False
                ) as f:
                    for sample in flattened_data:
                        f.write(json.dumps(sample) + "\n")
                    temp_baseline_file = f.name

                # Create new dataset adapter with flattened file
                baseline_dataset_adapter = JSONDatasetAdapter({"input"}, {"answer"})
                baseline_dataset_adapter.adapt(data_source=temp_baseline_file)

                print(
                    f"🔍 DEBUG - Created baseline dataset from temp file: {temp_baseline_file}"
                )
                print(
                    f"🔍 DEBUG - Baseline dataset samples: {len(baseline_dataset_adapter.standardized_dataset)}"
                )
            else:
                baseline_dataset_adapter = test_dataset

            # Check if this is a "Further Optimization" with few-shot examples
            baseline_few_shot_examples = config.get("baseline_few_shot_examples", [])
            if baseline_few_shot_examples:
                print(
                    f"🔍 DEBUG - Adding {len(baseline_few_shot_examples)} few-shot examples to baseline prompt"
                )
                # Add few-shot examples to prompt adapter for accurate baseline evaluation
                for example in baseline_few_shot_examples:
                    prompt_adapter.add_few_shot(example)
                db.add_optimization_log(
                    optimization_id,
                    "info",
                    f"📝 Added {len(baseline_few_shot_examples)} few-shot examples to baseline evaluation",
                )

            baseline_evaluator = Evaluator(
                prompt_adapter,
                baseline_dataset_adapter,
                original_metric,
                inference_adapter,
            )
            model_id = NOVA_MODELS[f"nova-{model_mode}"]["id"]

            # DEBUG: Check what max_tokens the model should use
            expected_max_tokens = NOVA_MODELS[f"nova-{model_mode}"]["max_tokens"]
            print(f"🔍 BEDROCK CONFIG - Model ID: {model_id}")
            print(f"🔍 BEDROCK CONFIG - Expected max_tokens: {expected_max_tokens}")
            print(
                f"🔍 BEDROCK CONFIG - Model config: {NOVA_MODELS[f'nova-{model_mode}']}"
            )

            print(f"🔍 DEBUG - About to call aggregate_score with model_id: {model_id}")
            print(f"🔍 DEBUG - Baseline evaluator components:")
            print(f"  - prompt_adapter: {type(prompt_adapter)}")
            print(
                f"  - baseline_dataset_adapter: {type(baseline_dataset_adapter)} with {len(baseline_dataset_adapter.standardized_dataset)} samples"
            )
            print(f"  - original_metric: {type(original_metric)} - {original_metric}")
            print(f"  - inference_adapter: {type(inference_adapter)}")

            # Test what the metric returns
            if hasattr(original_metric, "apply"):
                test_result = original_metric.apply(
                    '{"category": "test"}', '{"category": "test"}'
                )
                print(
                    f"🔍 DEBUG - Metric apply() returns: {test_result} (type: {type(test_result)})"
                )
                if isinstance(test_result, dict):
                    print(
                        f"🔍 DEBUG - ERROR: Metric returns dict, but SDK expects float!"
                    )
                    print(f"🔍 DEBUG - Dict keys: {list(test_result.keys())}")

            baseline_score = baseline_evaluator.aggregate_score(model_id=model_id)

            print(
                f"🔍 DEBUG - Raw baseline_score returned: {baseline_score} (type: {type(baseline_score)})"
            )

            # Clean up temp file if created
            if "temp_baseline_file" in locals():
                import os

                try:
                    os.unlink(temp_baseline_file)
                    print(f"🔍 DEBUG - Cleaned up temp baseline file")
                except:
                    pass

            print(f"🔍 DEBUG - Baseline score from SDK Evaluator: {baseline_score}")
            db.add_optimization_log(
                optimization_id,
                "success",
                f"✅ Baseline evaluation completed: {baseline_score}",
            )

        except Exception as e:
            import traceback

            print(f"❌ SDK Evaluator failed for baseline: {e}")
            print(f"❌ Full traceback: {traceback.format_exc()}")
            db.add_optimization_log(
                optimization_id, "error", f"❌ SDK Evaluator failed: {e}"
            )
            # Fallback to None if SDK evaluation fails
            baseline_score = None

        # 9. Calculate improvement and store results
        db.add_optimization_log(
            optimization_id,
            "info",
            f"📈 Baseline: {baseline_score}, Optimized: {optimized_score}",
        )

        # Handle None scores with defaults
        baseline_score = baseline_score if baseline_score is not None else 0.0
        optimized_score = optimized_score if optimized_score is not None else 0.0

        # Log the scores for debugging
        db.add_optimization_log(
            optimization_id,
            "debug",
            f"Scores - Baseline: {baseline_score}, Optimized: {optimized_score}",
        )

        improvement = (
            ((optimized_score - baseline_score) / baseline_score * 100)
            if baseline_score > 0
            else 0
        )

        baseline_display = (
            f"{baseline_score:.3f}" if baseline_score is not None else "N/A"
        )
        optimized_display = (
            f"{optimized_score:.3f}" if optimized_score is not None else "N/A"
        )
        db.add_optimization_log(
            optimization_id,
            "success",
            f"📈 Results: Baseline: {baseline_display}, Optimized: {optimized_display}, Improvement: {improvement:.1f}%",
        )

        # 10. Save optimized prompt adapter using official SDK method
        try:
            save_path = f"optimized_prompts/{optimization_id}/"
            optimized_prompt_adapter.save(save_path)
            db.add_optimization_log(
                optimization_id,
                "info",
                f"💾 Saved optimized prompt adapter to: {save_path}",
            )
        except Exception as e:
            db.add_optimization_log(
                optimization_id, "warning", f"⚠️ Could not save optimized adapter: {e}"
            )

        # 11. Extract optimized prompts using correct attributes (like notebook)
        try:
            # Access prompts directly like in notebook
            optimized_system = optimized_prompt_adapter.system_prompt
            optimized_user = optimized_prompt_adapter.user_prompt
            few_shot_count = len(optimized_prompt_adapter.few_shot_examples)

            db.add_optimization_log(
                optimization_id,
                "info",
                f"🔍 Extracted: System={bool(optimized_system)}, User={bool(optimized_user)}, Few-shot={few_shot_count}",
            )

            # Store FINAL results with LLM responses for evaluation display
            # Generate LLM responses to show what was actually evaluated

            # Get a test sample for response generation
            test_sample = (
                test_dataset.standardized_dataset[0]
                if test_dataset.standardized_dataset
                else None
            )

            optimized_response = None
            baseline_response = None

            if test_sample:
                try:
                    import boto3

                    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

                    # Generate optimized prompt response
                    if optimized_system:
                        model_id = NOVA_MODELS[f"nova-{model_mode}"]["id"]
                        model_max_tokens = NOVA_MODELS[f"nova-{model_mode}"][
                            "max_tokens"
                        ]
                        opt_response = bedrock.converse(
                            modelId=model_id,
                            messages=[
                                {
                                    "role": "user",
                                    "content": test_sample.get("input", ""),
                                }
                            ],
                            system=[{"text": optimized_system}],
                            inferenceConfig={
                                "maxTokens": model_max_tokens,
                                "temperature": 0.1,
                                "topP": 0.9,
                            },
                        )
                        optimized_response = opt_response["output"]["message"][
                            "content"
                        ][0]["text"]

                    # Generate baseline prompt response
                    baseline_system = (
                        system_prompt
                        if system_prompt.strip()
                        else "You are a helpful assistant."
                    )
                    baseline_user_content = user_prompt.replace(
                        "{{input}}", test_sample.get("input", "")
                    )

                    model_id = NOVA_MODELS[f"nova-{model_mode}"]["id"]
                    model_max_tokens = NOVA_MODELS[f"nova-{model_mode}"]["max_tokens"]
                    base_response = bedrock.converse(
                        modelId=model_id,
                        messages=[{"role": "user", "content": baseline_user_content}],
                        system=[{"text": baseline_system}],
                        inferenceConfig={
                            "maxTokens": model_max_tokens,
                            "temperature": 0.1,
                            "topP": 0.9,
                        },
                    )
                    baseline_response = base_response["output"]["message"]["content"][
                        0
                    ]["text"]

                except Exception as e:
                    print(f"🔍 DEBUG - Could not generate responses for display: {e}")

            # Store grouped results
            # 1. Optimized Prompt (System + User + Response)
            optimized_display = {
                "system": optimized_system
                if optimized_system
                else "No system prompt optimization",
                "user": optimized_user
                if optimized_user
                else "No user prompt optimization",
                "response": optimized_response
                if optimized_response
                else "No response generated",
                "few_shot_count": few_shot_count,
            }
            db.add_prompt_candidate(
                optimization_id,
                1,
                f"OPTIMIZED|{optimized_display}",
                None,
                optimized_score,
            )

            # 2. Baseline Prompt (System + User + Response)
            baseline_display = {
                "system": system_prompt if system_prompt else "No system prompt",
                "user": user_prompt if user_prompt else "No user prompt",
                "response": baseline_response
                if baseline_response
                else "No response generated",
            }
            db.add_prompt_candidate(
                optimization_id, 2, f"BASELINE|{baseline_display}", None, baseline_score
            )

            # 3. Few-shot Examples (separate display)
            if few_shot_count > 0:
                few_shot_examples = []
                for i, example in enumerate(
                    optimized_prompt_adapter.few_shot_examples[:5]
                ):  # Limit to first 5
                    few_shot_examples.append(
                        {
                            "number": i + 1,
                            "content": str(example)[
                                :2000
                            ],  # Increased limit for full examples
                        }
                    )

                few_shot_display = {
                    "count": few_shot_count,
                    "examples": few_shot_examples,
                }
                db.add_prompt_candidate(
                    optimization_id,
                    3,
                    f"FEWSHOT|{few_shot_display}",
                    None,
                    optimized_score,
                )

        except Exception as e:
            db.add_optimization_log(
                optimization_id, "error", f"❌ Could not extract prompts: {e}"
            )
            # Store originals as fallback
            db.add_prompt_candidate(
                optimization_id, 7, system_prompt[:500], None, optimized_score
            )
            db.add_prompt_candidate(
                optimization_id, 8, user_prompt[:300], None, optimized_score
            )
            db.add_prompt_candidate(
                optimization_id, 9, system_prompt[:500], None, baseline_score
            )
            db.add_prompt_candidate(
                optimization_id, 10, user_prompt[:300], None, baseline_score
            )

        # 10. Save results
        db.update_optimization_status(optimization_id, "Completed", 100)

        # Update the optimization record with results
        cursor = db.conn.cursor()
        cursor.execute(
            """
            UPDATE optimizations 
            SET improvement = ?, status = 'Completed', completed = datetime('now')
            WHERE id = ?
        """,
            (f"{improvement:.1f}%", optimization_id),
        )
        db.conn.commit()

        # Cleanup
        if os.path.exists(temp_dataset_path):
            os.remove(temp_dataset_path)

        print(f"✅ Optimization {optimization_id} completed successfully!")

    except Exception as e:
        db.add_optimization_log(
            optimization_id, "error", f"❌ Optimization failed: {str(e)}"
        )
        db.update_optimization_status(optimization_id, "Failed", 0)
        print(f"❌ Optimization {optimization_id} failed: {e}")
        raise


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python sdk_worker.py <optimization_id> <config_json>")
        sys.exit(1)

    optimization_id = sys.argv[1]
    run_optimization_worker(optimization_id)
