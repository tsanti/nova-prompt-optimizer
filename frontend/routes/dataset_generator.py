"""
Dataset Generator Routes
Handles AI-powered dataset generation
"""

from fasthtml.common import *
from database import Database
from components.layout import create_main_layout, create_card
from services.sample_generator import SampleGeneratorService as SampleGenerator
import json

# Global generator instance to maintain sessions
_generator_instance = None

def get_generator():
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = SampleGenerator()
    return _generator_instance


def setup_dataset_generator_routes(app):
    """Setup dataset generator routes"""
    
    @app.get("/datasets/generator")
    async def dataset_generator_page(request):
        """Smart Dataset Generator page"""
        
        # Get available prompts
        from database import Database
        db = Database()
        prompts = db.get_prompts()
        
        content = [
            create_card(
                title="Smart Dataset Generator",
                content=Div(
                    P("Generate datasets with annotation, steering, and inflation capabilities", cls="text-muted-foreground mb-4"),
                    
                    # Step 1: Select Prompt
                    Div(
                        H3("Step 1: Select Prompt", cls="text-lg font-semibold mb-2"),
                        Select(
                            Option("Select a prompt...", value="", selected=True),
                            *[Option(f"{p['name']} - {p.get('description', 'No description')[:50]}...", value=p['id']) for p in prompts],
                            id="prompt-select",
                            cls="w-full p-2 border rounded mb-3",
                            onchange="enableSampleCount()"
                        ),
                        cls="mb-4"
                    ),
                    
                    # Step 2: Initial Sample Count
                    Div(
                        H3("Step 2: Initial Sample Count", cls="text-lg font-semibold mb-2"),
                        Input(
                            type="number",
                            id="sample-count",
                            value="5",
                            min="1",
                            max="10",
                            disabled=True,
                            cls="w-32 p-2 border rounded mr-2"
                        ),
                        Button("Generate Initial Samples", onclick="generateInitialSamples()", id="generate-btn", disabled=True, cls="px-4 py-2 bg-primary text-primary-foreground rounded disabled:opacity-50"),
                        cls="mb-4"
                    ),
                    
                    # Step 3: Sample Review & Annotation (hidden initially)
                    Div(
                        H3("Step 3: Review & Annotate Samples", cls="text-lg font-semibold mb-2"),
                        Div(id="samples-container", cls="mb-3"),
                        Button("Regenerate with Feedback", onclick="regenerateSamples()", id="regenerate-btn", cls="px-4 py-2 bg-secondary text-secondary-foreground rounded mr-2"),
                        Button("Proceed to Inflation", onclick="showInflationStep()", id="proceed-btn", cls="px-4 py-2 bg-green-600 text-white rounded"),
                        id="annotation-step",
                        cls="mb-4 hidden"
                    ),
                    
                    # Step 4: Dataset Inflation (hidden initially)
                    Div(
                        H3("Step 4: Dataset Inflation", cls="text-lg font-semibold mb-2"),
                        P("Generate additional samples using your approved samples as few-shot examples", cls="text-sm text-gray-600 mb-2"),
                        Div(
                            Label("Target dataset size:", cls="block text-sm font-medium mb-1"),
                            Input(
                                type="number",
                                id="inflation-count",
                                value="50",
                                min="10",
                                max="500",
                                cls="w-32 p-2 border rounded mr-2"
                            ),
                            Button("Inflate Dataset", onclick="inflateDataset()", id="inflate-btn", cls="px-4 py-2 bg-purple-600 text-white rounded"),
                            cls="mb-3"
                        ),
                        Div(id="inflation-progress", cls="hidden"),
                        id="inflation-step",
                        cls="mb-4 hidden"
                    ),
                    
                    # Results
                    Div(id="results-container")
                )
            ),
            
            # JavaScript
            Script("""
let currentSessionId = null;
let currentSamples = [];

function enableSampleCount() {
    const promptSelect = document.getElementById('prompt-select');
    const sampleCount = document.getElementById('sample-count');
    const generateBtn = document.getElementById('generate-btn');
    
    if (promptSelect.value) {
        sampleCount.disabled = false;
        generateBtn.disabled = false;
    }
}

async function generateInitialSamples() {
    const promptId = document.getElementById('prompt-select').value;
    const sampleCount = document.getElementById('sample-count').value;
    const generateBtn = document.getElementById('generate-btn');
    
    generateBtn.textContent = 'Generating...';
    generateBtn.disabled = true;
    
    try {
        const response = await fetch('/datasets/generator/generate-initial', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: 'prompt_id=' + promptId + '&sample_count=' + sampleCount
        });
        
        const result = await response.json();
        if (result.success) {
            currentSessionId = result.session_id;
            currentSamples = result.samples;
            displaySamples(result.samples);
            document.getElementById('annotation-step').classList.remove('hidden');
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Error generating samples: ' + error.message);
    }
    
    generateBtn.textContent = 'Generate Initial Samples';
    generateBtn.disabled = false;
}

function displaySamples(samples) {
    const container = document.getElementById('samples-container');
    let html = '';
    for (let i = 0; i < samples.length; i++) {
        const sample = samples[i];
        // Handle nested objects in output
        let outputText = sample.answer_text;
        if (typeof outputText === 'object') {
            outputText = JSON.stringify(outputText, null, 2);
        }
        
        html += '<div class="border rounded p-3 mb-3">';
        html += '<div class="mb-2"><label class="block text-sm font-medium">Input:</label>';
        html += '<div class="p-2 bg-gray-50 rounded">' + sample.input_text + '</div></div>';
        html += '<div class="mb-2"><label class="block text-sm font-medium">Output:</label>';
        html += '<textarea id="output-' + i + '" class="w-full p-2 border rounded" rows="3">' + outputText + '</textarea></div>';
        html += '<div><label class="block text-sm font-medium">Feedback:</label>';
        html += '<input type="text" id="feedback-' + i + '" placeholder="Optional feedback for improvement" class="w-full p-2 border rounded"></div>';
        html += '</div>';
    }
    container.innerHTML = html;
}

async function regenerateSamples() {
    console.log('=== REGENERATE DEBUG ===');
    console.log('currentSessionId:', currentSessionId);
    console.log('currentSamples:', currentSamples);
    
    const annotations = [];
    for (let i = 0; i < currentSamples.length; i++) {
        const annotation = {
            id: currentSamples[i].id,
            corrected_output: document.getElementById('output-' + i).value,
            feedback: document.getElementById('feedback-' + i).value
        };
        annotations.push(annotation);
        console.log('Annotation ' + i + ':', annotation);
    }
    
    console.log('All annotations:', annotations);
    
    try {
        console.log('Sending request to improve-samples...');
        
        // Use FormData to properly encode the data
        const formData = new FormData();
        formData.append('session_id', currentSessionId);
        formData.append('annotations', JSON.stringify(annotations));
        
        const response = await fetch('/datasets/generator/improve-samples', {
            method: 'POST',
            body: formData
        });
        
        console.log('Response status:', response.status);
        const result = await response.json();
        console.log('Response result:', result);
        
        if (result.success) {
            console.log('Success! Updating samples...');
            currentSamples = result.samples;
            displaySamples(result.samples);
        } else {
            console.error('Error from server:', result.error);
            alert('Error: ' + result.error);
        }
    } catch (error) {
        console.error('Network error:', error);
        alert('Error regenerating samples: ' + error.message);
    }
}

function showInflationStep() {
    document.getElementById('inflation-step').classList.remove('hidden');
}

async function inflateDataset() {
    const inflationCount = document.getElementById('inflation-count').value;
    const inflateBtn = document.getElementById('inflate-btn');
    const progressDiv = document.getElementById('inflation-progress');
    
    inflateBtn.textContent = 'Inflating...';
    inflateBtn.disabled = true;
    progressDiv.classList.remove('hidden');
    progressDiv.innerHTML = '<p>Generating additional samples...</p>';
    
    try {
        const response = await fetch('/datasets/generator/generate-more', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: 'session_id=' + currentSessionId + '&num_samples=' + inflationCount
        });
        
        const result = await response.json();
        if (result.success) {
            progressDiv.innerHTML = '<div class="p-3 bg-green-50 border border-green-200 rounded">' +
                '<p class="text-green-800">✅ Successfully generated ' + result.samples.length + ' additional samples!</p>' +
                '<p class="text-sm text-green-600">Total dataset size: ' + result.total_samples + ' samples</p>' +
                '<button onclick="finalizeDataset()" class="mt-2 px-4 py-2 bg-green-600 text-white rounded">Save Dataset</button>' +
                '</div>';
        } else {
            progressDiv.innerHTML = '<p class="text-red-600">Error: ' + result.error + '</p>';
        }
    } catch (error) {
        progressDiv.innerHTML = '<p class="text-red-600">Error: ' + error.message + '</p>';
    }
    
    inflateBtn.textContent = 'Inflate Dataset';
    inflateBtn.disabled = false;
}

async function finalizeDataset() {
    const datasetName = prompt('Enter a name for your dataset:');
    if (!datasetName) return;
    
    try {
        const response = await fetch('/datasets/generator/finalize', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: 'session_id=' + currentSessionId + '&dataset_name=' + datasetName
        });
        
        const result = await response.json();
        if (result.success) {
            alert('Dataset saved successfully!');
            window.location.href = '/datasets';
        } else {
            alert('Error saving dataset: ' + result.error);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}
            """)
        ]
        
        return create_main_layout(
            "Smart Dataset Generator",
            Div(*content),
            current_page="datasets"
        )

    @app.post("/datasets/generator/generate-initial")
    async def generate_initial_samples(request):
        """Generate initial samples from selected prompt"""
        try:
            form_data = await request.form()
            prompt_id = form_data.get('prompt_id', '')
            sample_count = int(form_data.get('sample_count', 5))
            
            if not prompt_id:
                return {"success": False, "error": "Missing prompt ID"}
            
            # Get prompt content
            from database import Database
            db = Database()
            prompt_data = db.get_prompt(prompt_id)
            
            if not prompt_data:
                return {"success": False, "error": "Prompt not found"}
            
            # Handle different possible field names for prompt content
            prompt_content = prompt_data.get('content') or prompt_data.get('system_prompt') or prompt_data.get('user_prompt') or prompt_data.get('prompt') or str(prompt_data)
            
            # Create session
            session_id = f"smart_{hash(prompt_content) % 100000}"
            
            # Generate samples using the prompt content
            generator = get_generator()
            
            # Create a simple checklist object with the prompt content
            class PromptChecklist:
                def __init__(self, content):
                    self.original_prompt = content
                    self.prompt_content = content
            
            checklist = PromptChecklist(prompt_content)
            result = generator.generate_unique_questions(checklist, "us.amazon.nova-premier-v1:0")
            
            if result["success"]:
                # Convert samples to SampleRecord format
                from services.sample_generator import SampleRecord, GenerationSession
                samples = []
                for i, sample_data in enumerate(result["samples"]):
                    sample = SampleRecord(
                        id=f"{session_id}_{i}",
                        input_text=sample_data.get('input', ''),
                        answer_text=sample_data.get('output', '')
                    )
                    samples.append(sample)
                
                # Store session
                session = GenerationSession(
                    session_id=session_id,
                    samples=samples,
                    generation_prompt=prompt_content
                )
                generator.sessions[session_id] = session
                
                return {
                    "success": True,
                    "session_id": session_id,
                    "samples": [{"id": s.id, "input_text": s.input_text, "answer_text": s.answer_text} for s in samples]
                }
            else:
                return {"success": False, "error": result.get("error", "Failed to generate samples")}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    @app.post("/datasets/generator/start-conversation")
    async def start_conversation(request):
        """Start AI conversation for dataset requirements"""
        try:
            form_data = await request.form()
            user_message = form_data.get('message', '').strip()
            
            if not user_message:
                return {"success": False, "error": "Please provide a message"}
            
            # Initialize conversation with sample generator
            generator = get_generator()
            session_id = f"conv_{hash(user_message) % 100000}"
            
            # Start conversation
            response = await generator.start_conversation(user_message, session_id)
            
            return {
                "success": True,
                "session_id": session_id,
                "ai_response": response.get("ai_response", ""),
                "ready_for_generation": response.get("ready_for_generation", False)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.post("/datasets/generator/continue-conversation")
    async def continue_conversation(request):
        """Continue AI conversation"""
        try:
            form_data = await request.form()
            session_id = form_data.get('session_id', '')
            user_message = form_data.get('message', '').strip()
            
            if not session_id or not user_message:
                return {"success": False, "error": "Missing session or message"}
            
            generator = get_generator()
            response = await generator.continue_conversation(session_id, user_message)
            
            return {
                "success": True,
                "ai_response": response.get("ai_response", ""),
                "ready_for_generation": response.get("ready_for_generation", False)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.get("/datasets/generator/progress/{session_id}")
    async def get_generation_progress(session_id: str):
        """Get generation progress for a session"""
        try:
            # Check if there's a progress file for this session
            progress_file = f"data/generation_progress_{session_id}.json"
            if os.path.exists(progress_file):
                with open(progress_file, 'r') as f:
                    progress = json.load(f)
                return progress
            else:
                return {"current": 0, "total": 0, "status": "not_started"}
        except Exception as e:
            return {"current": 0, "total": 0, "status": "error", "error": str(e)}

    @app.post("/datasets/generator/generate-samples")
    async def generate_samples(request):
        """Generate initial samples"""
        try:
            form_data = await request.form()
            session_id = form_data.get('session_id', '')
            model_id = form_data.get('model_id', 'us.amazon.nova-micro-v1:0')
            
            if not session_id:
                return {"success": False, "error": "Missing session ID"}
            
            generator = SampleGenerator(model_id=model_id)
            
            # Get generation config from conversation
            generation_config = generator.get_generation_config(session_id)
            if not generation_config:
                return {"success": False, "error": "No generation configuration found"}
            
            # Generate samples
            result = generator.generate_initial_samples(generation_config, session_id)
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.post("/datasets/generator/improve-samples")
    async def improve_samples(request):
        """Improve samples based on user feedback"""
        try:
            print("=== IMPROVE SAMPLES DEBUG ===")
            form_data = await request.form()
            session_id = form_data.get('session_id', '')
            annotations_json = form_data.get('annotations', '[]')
            
            print(f"Session ID: {session_id}")
            print(f"Annotations JSON: {annotations_json}")
            
            if not session_id:
                print("ERROR: Missing session ID")
                return {"success": False, "error": "Missing session ID"}
            
            annotations = json.loads(annotations_json)
            print(f"Parsed annotations: {annotations}")
            
            if not annotations:
                print("ERROR: No annotations provided")
                return {"success": False, "error": "No annotations provided"}
            
            generator = get_generator()
            print(f"Generator sessions: {list(generator.sessions.keys())}")
            
            result = generator.improve_samples(session_id, annotations)
            print(f"Generator result: {result}")
            
            return result
            
        except Exception as e:
            print(f"ERROR in improve_samples: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    @app.post("/datasets/generator/generate-more")
    async def generate_more_samples(request):
        """Generate additional samples"""
        try:
            form_data = await request.form()
            session_id = form_data.get('session_id', '')
            num_samples = int(form_data.get('num_samples', 5))
            
            if not session_id:
                return {"success": False, "error": "Missing session ID"}
            
            generator = get_generator()
            result = generator.generate_more_samples(session_id, num_samples)
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.post("/datasets/generator/finalize")
    async def finalize_dataset(request):
        """Finalize and save generated dataset"""
        try:
            form_data = await request.form()
            session_id = form_data.get('session_id', '')
            dataset_name = form_data.get('dataset_name', '').strip()
            
            if not session_id or not dataset_name:
                return {"success": False, "error": "Missing session ID or dataset name"}
            
            generator = get_generator()
            result = generator.finalize_dataset(session_id, dataset_name)
            
            if result.get("success"):
                # Save to database
                db = Database()
                
                # Get file info
                file_path = result.get("file_path", "")
                file_size = f"{os.path.getsize(file_path) / 1024:.1f} KB" if file_path and os.path.exists(file_path) else "0 KB"
                row_count = result.get("sample_count", 0)
                
                dataset_id = db.create_dataset(
                    name=dataset_name,
                    file_type="JSONL",
                    file_size=file_size,
                    row_count=row_count,
                    file_path=file_path
                )
                
                return {
                    "success": True,
                    "dataset_id": dataset_id,
                    "message": "Dataset saved successfully"
                }
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}
