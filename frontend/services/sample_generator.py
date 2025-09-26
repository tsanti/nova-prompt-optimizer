"""
Sample generation service for AI dataset creation.
Generates initial samples, processes annotations, and handles iterative refinement.
"""

import json
import boto3
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

class GeneratedSample(BaseModel):
    """Flexible model for LLM-generated sample records"""
    input: str = Field(..., description="The user's input/question")
    output: Any = Field(..., description="The AI's response in the specified format (can be string, dict, or list)")
    
    def get_output_as_string(self) -> str:
        """Convert output to string format for consistency"""
        if isinstance(self.output, str):
            return self.output
        elif isinstance(self.output, (dict, list)):
            return json.dumps(self.output, indent=2, ensure_ascii=False)
        else:
            return str(self.output)
    
    @classmethod
    def from_llm_response(cls, response_data: Dict[str, Any]) -> 'GeneratedSample':
        """Create GeneratedSample from LLM response with flexible output handling"""
        input_text = response_data.get('input', '')
        output_data = response_data.get('output', '')
        
        # Handle cases where output might be nested or formatted differently
        if isinstance(output_data, dict):
            # If output is a dict, keep it as is (our model now supports this)
            return cls(input=input_text, output=output_data)
        elif isinstance(output_data, str):
            # If output is already a string, use it directly
            return cls(input=input_text, output=output_data)
        else:
            # Convert other types to string
            return cls(input=input_text, output=str(output_data))


@dataclass
class SampleRecord:
    """Individual sample record with annotation support"""
    id: str
    input_text: str
    answer_text: str
    annotations: List[str] = None
    quality_score: float = 0.0
    
    def __post_init__(self):
        if self.annotations is None:
            self.annotations = []


@dataclass
class GenerationSession:
    """Tracks sample generation and iteration state"""
    session_id: str
    samples: List[SampleRecord]
    generation_prompt: str
    iteration_count: int = 0
    feedback_summary: str = ""


class SampleGeneratorService:
    """Service for generating and refining dataset samples"""
    
    def __init__(self, region_name: str = "us-east-1"):
        self.bedrock = boto3.client('bedrock-runtime', region_name=region_name)
        self.model_id = "us.amazon.nova-premier-v1:0"
        self.sessions: Dict[str, GenerationSession] = {}
    
    def generate_unique_questions(self, checklist, model_id: str) -> Dict[str, Any]:
        """Generate 5 unique samples based on the original prompt"""
        try:
            # Use the actual prompt content to infer what to generate
            prompt_content = getattr(checklist, 'original_prompt', '') or getattr(checklist, 'prompt_content', '')
            
            prompt = f"""
            Analyze this prompt and generate 5 diverse training samples for it:
            
            PROMPT TO ANALYZE:
            {prompt_content}
            
            Based on the prompt above:
            1. Identify what type of inputs it expects
            2. Understand the expected output format
            3. Generate 5 varied, realistic examples that would work with this prompt
            
            Make each sample:
            - Realistic and varied in content with detailed, comprehensive responses
            - Different scenarios/contexts covering various edge cases
            - Appropriate for the prompt's domain with rich context
            - Diverse in complexity and style, ranging from simple to complex cases
            - Longer, more detailed inputs and outputs (aim for 2-3 sentences minimum for inputs, detailed responses for outputs)
            
            Return JSON array with objects: [{{"input": "detailed sample input with context", "output": "comprehensive expected output"}}, ...]
            """
            
            response = self._call_bedrock_with_model(prompt, model_id)
            
            try:
                # Clean up the response text
                response_text = response.strip()
                
                # Remove markdown code blocks
                if response_text.startswith('```json'):
                    response_text = response_text[7:]
                elif response_text.startswith('```'):
                    response_text = response_text[3:]
                    
                if response_text.endswith('```'):
                    response_text = response_text[:-3]
                
                response_text = response_text.strip()
                
                # Try to find JSON array in the response
                import re
                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(0)
                
                samples = json.loads(response_text, strict=False)
                
                if isinstance(samples, list) and len(samples) > 0:
                    return {
                        "success": True,
                        "samples": samples
                    }
                else:
                    return {"success": False, "error": "Invalid questions format"}
                    
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                print(f"Response text: {response_text[:500]}...")
                return {"success": False, "error": f"Invalid JSON response: {str(e)}"}
                
        except Exception as e:
            print(f"Error generating questions: {e}")
            return {"success": False, "error": str(e)}
    
    def process_question_to_sample(self, checklist, question: str, model_id: str, sample_number: int) -> Dict[str, Any]:
        """Process a single question to generate the complete XML response"""
        try:
            print(f"🔍 DEBUG - Processing question: {repr(question)} (type: {type(question)})")
            
            # Ensure question is a string
            question_str = str(question) if question else "No question provided"
            
            prompt = f"""
            You are a {checklist.role_persona} responding to this user question:
            
            USER QUESTION: {question_str}
            
            Analyze this question and respond using the exact format specified in the requirements:
            
            {output_format_text}
            
            Return JSON: {{"input": "{question_str}", "output": "complete response in the exact format specified above"}}
            """
            
            response = self._call_bedrock_with_model(prompt, model_id)
            
            try:
                # Remove markdown if present
                response_text = response.strip()
                if response_text.startswith('```json'):
                    response_text = response_text[7:]
                if response_text.endswith('```'):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                sample_data = json.loads(response_text, strict=False)
                validated_sample = GeneratedSample(**sample_data)
                
                return {
                    "success": True,
                    "sample": validated_sample.model_dump()
                }
                
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                return {"success": False, "error": f"Invalid JSON response: {str(e)}"}
            except Exception as e:
                print(f"Validation error: {e}")
                return {"success": False, "error": f"Invalid sample format: {str(e)}"}
                
        except Exception as e:
            print(f"Error processing question: {e}")
            return {"success": False, "error": str(e)}
    
    def generate_single_sample_from_checklist(self, checklist, model_id: str, sample_number: int) -> Dict[str, Any]:
        """Generate a single sample record from checklist"""
        try:
            # Extract actual format from the output format description
            output_format_text = str(checklist.output_format)
            print(f"🔍 DEBUG - Output format text: {output_format_text}")
            
            prompt = f"""
            Generate a training sample for IT support evaluation.
            
            Context: {checklist.role_persona}
            Task: {checklist.task_goal}
            Domain: {checklist.domain_expertise}
            
            Output format required: {output_format_text}
            
            Create 1 unique tech support question and respond using the EXACT format specified above.
            
            Return JSON: {{"input": "realistic user tech question", "output": "complete response in the exact format specified"}}
            
            IMPORTANT:
            - Generate varied questions: WiFi, email, printing, software, hardware
            - Use the EXACT output format structure from the requirements
            - Include all required fields and reasoning elements
            - Make each question unique (sample #{sample_number})
            """
            
            # Call Bedrock with specified model
            response = self._call_bedrock_with_model(prompt, model_id)
            print(f"🔍 DEBUG - Raw LLM response: '{response}'")
            
            # Parse the response using Pydantic model
            try:
                response_text = response.strip()
                if not response_text:
                    return {"success": False, "error": "Empty response from LLM"}
                
                # Remove markdown code blocks if present
                if '```json' in response_text:
                    # Extract JSON from between ```json and ```
                    start = response_text.find('```json') + 7
                    end = response_text.find('```', start)
                    if end != -1:
                        response_text = response_text[start:end].strip()
                    else:
                        response_text = response_text[start:].strip()
                elif response_text.startswith('```json'):
                    response_text = response_text[7:]  # Remove ```json
                    if response_text.endswith('```'):
                        response_text = response_text[:-3]  # Remove ```
                
                response_text = response_text.strip()
                
                # Parse JSON with proper handling of control characters
                sample_data = json.loads(response_text, strict=False)
                
                # Use the flexible factory method to handle complex output structures
                validated_sample = GeneratedSample.from_llm_response(sample_data)
                
                # Convert to dict with proper output handling
                sample_dict = validated_sample.model_dump()
                
                # Always provide a string version for compatibility
                sample_dict['output_string'] = validated_sample.get_output_as_string()
                
                return {
                    "success": True,
                    "sample": sample_dict
                }
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                print(f"Raw response was: '{response}'")
                return {"success": False, "error": f"Invalid JSON response: {str(e)}"}
            except Exception as e:
                print(f"Validation error: {e}")
                return {"success": False, "error": f"Invalid sample format: {str(e)}"}
            
        except Exception as e:
            print(f"Error generating single sample: {e}")
            return {"success": False, "error": str(e)}
    
    def generate_single_sample(self, session_id: str, model_id: str, sample_number: int) -> Dict[str, Any]:
        """Generate a single sample record"""
        try:
            # Get session data
            session_data = self.sessions.get(session_id)
            if not session_data:
                return {"success": False, "error": "Session not found"}
            
            # Create a simple prompt for single sample generation
            prompt = f"""
            Generate 1 sample record for this dataset:
            
            Role: {session_data.checklist.role_persona}
            Task: {session_data.checklist.task_goal}
            Input Format: {session_data.checklist.input_format}
            Output Format: {session_data.checklist.output_format}
            Domain: {session_data.checklist.domain_expertise}
            
            Generate exactly 1 realistic sample with:
            - input: [realistic input example]
            - output: [expected output following the specified format]
            
            Return as JSON: {{"input": "...", "output": "..."}}
            """
            
            # Call Bedrock with specified model
            response = self._call_bedrock_with_model(prompt, model_id)
            
            # Parse the response
            import json
            try:
                sample_data = json.loads(response.strip())
                return {
                    "success": True,
                    "sample": sample_data
                }
            except json.JSONDecodeError:
                # Fallback parsing
                return {
                    "success": True,
                    "sample": {
                        "input": f"Sample input {sample_number}",
                        "output": response.strip()
                    }
                }
            
        except Exception as e:
            print(f"Error generating single sample: {e}")
            return {"success": False, "error": str(e)}
    
    def _call_bedrock_with_model(self, prompt: str, model_id: str) -> str:
        """Call Bedrock with specific model"""
        try:
            response = self.bedrock.invoke_model(
                modelId=model_id,
                body=json.dumps({
                    "messages": [{"role": "user", "content": [{"text": prompt}]}],
                    "inferenceConfig": {
                        "maxTokens": 2000,
                        "temperature": 0.7
                    }
                })
            )
            
            result = json.loads(response['body'].read())
            content = result['output']['message']['content'][0]['text']
            
            # Check if response is empty or too short
            if not content or len(content.strip()) < 10:
                print(f"Warning: Short or empty response: '{content}'")
                return ""
            
            return content
            
        except Exception as e:
            print(f"Error calling Bedrock: {e}")
            return ""
    
    def generate_initial_samples(self, generation_config: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Generate initial 5 samples based on requirements"""
        
        generation_prompt = generation_config.get('generation_prompt', '')
        
        try:
            # Generate samples using AI
            samples_text = self._call_bedrock(generation_prompt)
            
            # Parse generated samples
            samples = self._parse_generated_samples(samples_text, session_id)
            
            # Create generation session
            session = GenerationSession(
                session_id=session_id,
                samples=samples,
                generation_prompt=generation_prompt
            )
            self.sessions[session_id] = session
            
            return {
                "success": True,
                "session_id": session_id,
                "samples": [self._sample_to_dict(sample) for sample in samples],
                "generation_prompt": generation_prompt
            }
            
        except Exception as e:
            print(f"Error generating samples: {e}")
            return {
                "success": False,
                "error": str(e),
                "samples": []
            }
    
    def process_annotations(self, session_id: str, sample_annotations: Dict[str, List[str]]) -> Dict[str, Any]:
        """Process user annotations and generate improved samples"""
        
        if session_id not in self.sessions:
            return {"success": False, "error": "Session not found"}
        
        session = self.sessions[session_id]
        
        # Update samples with annotations
        for sample in session.samples:
            if sample.id in sample_annotations:
                sample.annotations = sample_annotations[sample.id]
        
        # Generate feedback summary
        feedback_summary = self._analyze_annotations(session.samples)
        session.feedback_summary = feedback_summary
        
        # Generate improved prompt
        improved_prompt = self._create_improved_prompt(session)
        
        try:
            # Generate new samples with improvements
            improved_samples_text = self._call_bedrock(improved_prompt)
            improved_samples = self._parse_generated_samples(improved_samples_text, session_id, iteration=session.iteration_count + 1)
            
            # Update session
            session.samples = improved_samples
            session.iteration_count += 1
            session.generation_prompt = improved_prompt
            
            return {
                "success": True,
                "session_id": session_id,
                "samples": [self._sample_to_dict(sample) for sample in improved_samples],
                "feedback_summary": feedback_summary,
                "iteration": session.iteration_count
            }
            
        except Exception as e:
            print(f"Error processing annotations: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def generate_full_dataset(self, session_id: str, num_records: int, output_format: str) -> Dict[str, Any]:
        """Generate full dataset based on refined samples"""
        
        if session_id not in self.sessions:
            return {"success": False, "error": "Session not found"}
        
        session = self.sessions[session_id]
        
        # Create batch generation prompt
        batch_prompt = self._create_batch_generation_prompt(session, num_records)
        
        try:
            # Generate full dataset
            dataset_text = self._call_bedrock(batch_prompt)
            
            # Parse and format dataset
            dataset_records = self._parse_dataset_batch(dataset_text)
            
            # Format according to requested output format
            if output_format.lower() == 'csv':
                formatted_data = self._format_as_csv(dataset_records)
                file_extension = 'csv'
            else:
                formatted_data = self._format_as_jsonl(dataset_records)
                file_extension = 'jsonl'
            
            return {
                "success": True,
                "dataset": formatted_data,
                "format": output_format,
                "file_extension": file_extension,
                "record_count": len(dataset_records),
                "session_id": session_id
            }
            
        except Exception as e:
            print(f"Error generating full dataset: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _parse_generated_samples(self, samples_text: str, session_id: str, iteration: int = 0) -> List[SampleRecord]:
        """Parse AI-generated samples into SampleRecord objects"""
        
        print(f"=== PARSE_GENERATED_SAMPLES DEBUG ===")
        print(f"Raw input: {samples_text[:500]}...")
        
        samples = []
        
        try:
            # Clean up markdown and extract JSON
            cleaned_text = samples_text.strip()
            
            # Remove markdown code blocks
            import re
            
            # First try to find ```json blocks
            json_blocks = re.findall(r'```json\s*(.*?)\s*```', cleaned_text, re.DOTALL | re.IGNORECASE)
            if json_blocks:
                cleaned_text = json_blocks[0]
                print(f"Found JSON block: {cleaned_text[:200]}...")
            else:
                # Try to find any ``` blocks
                code_blocks = re.findall(r'```\s*(.*?)\s*```', cleaned_text, re.DOTALL)
                if code_blocks:
                    cleaned_text = code_blocks[0]
                    print(f"Found code block: {cleaned_text[:200]}...")
            
            # Try to extract JSON array from anywhere in the text
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', cleaned_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(0)
                print(f"Extracted JSON array: {cleaned_text[:200]}...")
            
            # Parse the JSON
            json_samples = json.loads(cleaned_text)
            print(f"Successfully parsed {len(json_samples)} samples")
            
            for i, sample in enumerate(json_samples):
                print(f"Sample {i}: {sample}")
                samples.append(SampleRecord(
                    id=f"{session_id}_sample_{iteration}_{i}",
                    input_text=sample.get('input', ''),
                    answer_text=sample.get('output', sample.get('answer', ''))
                ))
                
        except Exception as e:
            print(f"JSON parsing failed: {e}")
            print(f"Trying line-by-line parsing...")
            
            # Fallback: try line-by-line parsing
            try:
                lines = samples_text.strip().split('\n')
                sample_count = 0
                
                for line in lines:
                    line = line.strip()
                    if line and (line.startswith('{') or '"input"' in line):
                        try:
                            sample_data = json.loads(line)
                            samples.append(SampleRecord(
                                id=f"{session_id}_sample_{iteration}_{sample_count}",
                                input_text=sample_data.get('input', ''),
                                answer_text=sample_data.get('output', sample_data.get('answer', ''))
                            ))
                            sample_count += 1
                            print(f"Parsed line sample {sample_count}")
                        except json.JSONDecodeError:
                            continue
            except Exception as e2:
                print(f"Line parsing also failed: {e2}")
                
                # Last resort: create error samples
                samples = [SampleRecord(
                    id=f"{session_id}_error_0",
                    input_text="Error parsing AI response",
                    answer_text=f"Could not parse: {str(e)}"
                )]
        
        print(f"Returning {len(samples)} samples")
        return samples[:5]  # Ensure max 5 samples
    
    def _extract_samples_from_text(self, text: str, session_id: str, iteration: int) -> List[SampleRecord]:
        """Extract samples from unstructured text"""
        
        samples = []
        
        # Look for input/answer patterns
        import re
        
        # Pattern 1: "Input: ... Answer: ..."
        pattern1 = r'Input:\s*(.+?)\s*Answer:\s*(.+?)(?=Input:|$)'
        matches = re.findall(pattern1, text, re.DOTALL | re.IGNORECASE)
        
        for i, (input_text, answer_text) in enumerate(matches[:5]):
            samples.append(SampleRecord(
                id=f"{session_id}_sample_{iteration}_{i}",
                input_text=input_text.strip(),
                answer_text=answer_text.strip()
            ))
        
        return samples
    
    def _analyze_annotations(self, samples: List[SampleRecord]) -> str:
        """Analyze user annotations to create feedback summary"""
        
        all_annotations = []
        for sample in samples:
            all_annotations.extend(sample.annotations)
        
        if not all_annotations:
            return "No specific feedback provided."
        
        # Use AI to analyze annotations
        analysis_prompt = f"""
        Analyze these user annotations about generated dataset samples:
        
        ANNOTATIONS:
        {json.dumps(all_annotations, indent=2)}
        
        Summarize the key feedback themes and improvement areas:
        - What quality issues were identified?
        - What improvements are needed?
        - What patterns should be adjusted?
        
        Provide a concise summary for improving the next generation.
        """
        
        try:
            return self._call_bedrock(analysis_prompt)
        except:
            return "Feedback received: " + "; ".join(all_annotations[:3])
    
    def _create_improved_prompt(self, session: GenerationSession) -> str:
        """Create improved generation prompt based on feedback"""
        
        base_prompt = session.generation_prompt
        feedback = session.feedback_summary
        
        improved_prompt = f"""
        {base_prompt}
        
        IMPORTANT IMPROVEMENTS NEEDED:
        Based on user feedback: {feedback}
        
        Please address these specific issues in the new examples:
        - Improve quality based on the feedback above
        - Ensure more realistic and varied scenarios
        - Fix any format or content issues mentioned
        - Maintain consistency with the original requirements
        
        Generate exactly 5 improved examples.
        """
        
        return improved_prompt
    
    def _create_batch_generation_prompt(self, session: GenerationSession, num_records: int) -> str:
        """Create prompt for generating full dataset"""
        
        base_prompt = session.generation_prompt
        feedback = session.feedback_summary
        
        batch_prompt = f"""
        {base_prompt}
        
        QUALITY REQUIREMENTS:
        {feedback}
        
        Generate exactly {num_records} high-quality examples following the established pattern.
        
        Requirements:
        - Each example must have "input" and "answer" fields
        - Ensure maximum diversity in scenarios and language
        - Include edge cases and challenging examples (20% of total)
        - Maintain consistent quality and format
        - Use realistic, natural language
        
        Output format: One JSON object per line (JSONL format)
        {{"input": "example input", "answer": "expected answer"}}
        """
        
        return batch_prompt
    
    def _parse_dataset_batch(self, dataset_text: str) -> List[Dict[str, str]]:
        """Parse batch-generated dataset"""
        
        records = []
        lines = dataset_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line and (line.startswith('{') or '"input"' in line):
                try:
                    record = json.loads(line)
                    if 'input' in record and 'answer' in record:
                        records.append({
                            'input': record['input'],
                            'answer': record['answer']
                        })
                except json.JSONDecodeError:
                    continue
        
        return records
    
    def _format_as_jsonl(self, records: List[Dict[str, str]]) -> str:
        """Format records as JSONL"""
        return '\n'.join(json.dumps(record) for record in records)
    
    def _format_as_csv(self, records: List[Dict[str, str]]) -> str:
        """Format records as CSV"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['input', 'answer'])
        writer.writeheader()
        writer.writerows(records)
        
        return output.getvalue()
    
    def _sample_to_dict(self, sample: SampleRecord) -> Dict[str, Any]:
        """Convert SampleRecord to dictionary"""
        return {
            "id": sample.id,
            "input_text": sample.input_text,
            "answer_text": sample.answer_text,
            "annotations": sample.annotations,
            "quality_score": sample.quality_score
        }
    
    def _call_bedrock(self, prompt: str) -> str:
        """Call Bedrock API with the given prompt"""
        
        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "messages": [{"role": "user", "content": [{"text": prompt}]}],
                    "inferenceConfig": {
                        "maxTokens": 4000,
                        "temperature": 0.8
                    }
                })
            )
            
            response_body = json.loads(response['body'].read())
            return response_body['output']['message']['content'][0]['text']
            
        except ClientError as e:
            print(f"Bedrock API error: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error calling Bedrock: {e}")
            raise

    def improve_samples(self, session_id: str, annotations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Regenerate samples based on user annotations and feedback"""
        try:
            print(f"=== IMPROVE_SAMPLES DEBUG ===")
            print(f"Session ID: {session_id}")
            print(f"Available sessions: {list(self.sessions.keys())}")
            
            if session_id not in self.sessions:
                print(f"ERROR: Session {session_id} not found")
                return {"success": False, "error": "Session not found"}
            
            session = self.sessions[session_id]
            print(f"Session found: {session}")
            print(f"Session samples count: {len(session.samples)}")
            
            # Process annotations to update samples
            for annotation in annotations:
                sample_id = annotation.get('id')
                feedback = annotation.get('feedback', '')
                corrected_output = annotation.get('corrected_output', '')
                print(f"Processing annotation - ID: {sample_id}, Feedback: {feedback}")
                
                # Find and update the sample
                for sample in session.samples:
                    if sample.id == sample_id:
                        if corrected_output:
                            sample.answer_text = corrected_output
                            print(f"Updated sample {sample_id} output")
                        if feedback:
                            # Store feedback in annotations list
                            if not hasattr(sample, 'annotations') or sample.annotations is None:
                                sample.annotations = []
                            sample.annotations.append(feedback)
                            print(f"Added feedback to sample {sample_id}")
                        break
            
            # Generate feedback summary for regeneration
            feedback_summary = self._analyze_annotations(session.samples)
            print(f"Feedback summary: {feedback_summary}")
            
            # Create improved prompt based on feedback
            improved_prompt = f"""
Based on the following feedback from sample annotations:

{feedback_summary}

Original prompt: {session.generation_prompt}

Generate 5 improved samples that address the feedback. Each sample should:
1. Follow the corrected patterns shown in annotations
2. Avoid the issues mentioned in feedback
3. Maintain variety while improving quality

Output format: JSON array with objects containing 'input' and 'output' fields.
"""
            
            print(f"Calling Bedrock with improved prompt...")
            # Generate improved samples
            response = self._call_bedrock(improved_prompt)
            print(f"Bedrock response: {response[:200]}...")
            
            new_samples = self._parse_generated_samples(response, session_id, session.iteration_count)
            print(f"Parsed {len(new_samples)} new samples")
            
            # Update session with improved samples
            session.samples = new_samples
            session.iteration_count += 1
            session.feedback_summary = feedback_summary
            
            result = {
                "success": True,
                "samples": [self._sample_to_dict(s) for s in new_samples],
                "message": f"Generated {len(new_samples)} improved samples based on your feedback"
            }
            print(f"Returning result: {result}")
            return result
            
        except Exception as e:
            print(f"ERROR in improve_samples: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def generate_more_samples(self, session_id: str, num_samples: int = 10) -> Dict[str, Any]:
        """Generate additional samples using existing samples as few-shot examples"""
        try:
            print(f"=== GENERATE_MORE_SAMPLES DEBUG ===")
            print(f"Requested samples: {num_samples}")
            
            if session_id not in self.sessions:
                return {"success": False, "error": "Session not found"}
            
            session = self.sessions[session_id]
            
            if not session.samples:
                return {"success": False, "error": "No existing samples to use as examples"}
            
            # Use best samples as few-shot examples (samples without negative feedback)
            good_samples = [s for s in session.samples if not hasattr(s, 'feedback') or not s.feedback or 'good' in s.feedback.lower()]
            if not good_samples:
                good_samples = session.samples[:3]  # Use first 3 if no explicitly good ones
            
            # Create few-shot prompt
            few_shot_examples = []
            for sample in good_samples[:5]:  # Max 5 examples
                few_shot_examples.append(f"Input: {sample.input_text}\nOutput: {sample.answer_text}")
            
            few_shot_text = "\n\n".join(few_shot_examples)
            
            # Generate samples in batches (max 10 per call to avoid token limits)
            all_new_samples = []
            batch_size = min(10, num_samples)
            num_batches = (num_samples + batch_size - 1) // batch_size  # Ceiling division
            
            print(f"Generating {num_samples} samples in {num_batches} batches of {batch_size}")
            
            for batch_num in range(num_batches):
                remaining_samples = num_samples - len(all_new_samples)
                current_batch_size = min(batch_size, remaining_samples)
                
                print(f"Batch {batch_num + 1}/{num_batches}: generating {current_batch_size} samples")
                
                expansion_prompt = f"""
You are generating additional samples for a dataset. Use the following examples as a guide for the style, format, and quality expected:

EXAMPLES:
{few_shot_text}

Original task: {session.generation_prompt}

Generate {current_batch_size} NEW samples that:
1. Follow the same format and style as the examples
2. Cover different scenarios and variations
3. Maintain the same quality and detail level
4. Are diverse and don't repeat the examples or previous batches

Output format: JSON array with objects containing 'input' and 'output' fields.
"""
                
                # Generate batch of samples
                response = self._call_bedrock(expansion_prompt)
                batch_samples = self._parse_generated_samples(response, session_id, session.iteration_count + batch_num)
                
                print(f"Batch {batch_num + 1} generated {len(batch_samples)} samples")
                all_new_samples.extend(batch_samples)
                
                # Stop if we have enough samples
                if len(all_new_samples) >= num_samples:
                    break
            
            # Trim to exact number requested
            all_new_samples = all_new_samples[:num_samples]
            print(f"Total generated: {len(all_new_samples)} samples")
            
            # Add to existing samples
            session.samples.extend(all_new_samples)
            session.iteration_count += 1
            
            return {
                "success": True,
                "samples": [self._sample_to_dict(s) for s in all_new_samples],
                "total_samples": len(session.samples),
                "message": f"Generated {len(all_new_samples)} additional samples using {len(good_samples)} examples"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def finalize_dataset(self, session_id: str, dataset_name: str) -> Dict[str, Any]:
        """Finalize and save the generated dataset"""
        try:
            import os
            import json
            from datetime import datetime
            
            print(f"=== FINALIZE_DATASET DEBUG ===")
            print(f"Session ID: {session_id}")
            print(f"Dataset name: {dataset_name}")
            
            if session_id not in self.sessions:
                return {"success": False, "error": "Session not found"}
            
            session = self.sessions[session_id]
            
            if not session.samples:
                return {"success": False, "error": "No samples to save"}
            
            # Convert samples to JSON format
            dataset_samples = []
            for sample in session.samples:
                dataset_samples.append({
                    "input": sample.input_text,
                    "output": sample.answer_text
                })
            
            # Create dataset content
            dataset_content = {
                "name": dataset_name,
                "description": f"Generated dataset with {len(dataset_samples)} samples",
                "samples": dataset_samples,
                "metadata": {
                    "generation_prompt": session.generation_prompt,
                    "total_samples": len(dataset_samples),
                    "iterations": session.iteration_count,
                    "created_at": str(datetime.now())
                }
            }
            
            # Save to file
            # Create uploads directory if it doesn't exist (same as uploaded datasets)
            uploads_dir = "uploads"
            os.makedirs(uploads_dir, exist_ok=True)
            
            # Generate filename
            safe_name = "".join(c for c in dataset_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            filename = f"{safe_name}_{session_id}.jsonl"
            file_path = os.path.join(uploads_dir, filename)
            
            # Save as JSONL format (one JSON object per line)
            with open(file_path, 'w', encoding='utf-8') as f:
                for sample in dataset_samples:
                    f.write(json.dumps(sample) + '\n')
            
            print(f"Saved {len(dataset_samples)} samples to {file_path}")
            
            return {
                "success": True,
                "message": f"Successfully saved {len(dataset_samples)} samples",
                "file_path": file_path,
                "filename": filename,
                "sample_count": len(dataset_samples)
            }
            
        except Exception as e:
            print(f"ERROR in finalize_dataset: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
