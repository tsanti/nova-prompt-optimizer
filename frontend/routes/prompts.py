"""
Prompt Management Routes
Handles prompt CRUD operations
"""

from fasthtml.common import *
from database import Database
from components.layout import create_main_layout, create_card


def setup_prompt_routes(app):
    """Setup prompt management routes"""
    
    @app.get("/prompts")
    async def prompts_page(request):
        """Prompts management page"""
        
        db = Database()
        prompts = db.get_prompts()
        
        prompt_rows = []
        for prompt in prompts:
            variables = prompt.get('variables', {})
            
            # Handle both dictionary and list formats for variables
            if isinstance(variables, dict):
                system_prompt = variables.get('system_prompt', '')
                user_prompt = variables.get('user_prompt', '')
            else:
                # Legacy format - variables is a list
                system_prompt = ''
                user_prompt = ', '.join(variables) if variables else ''
            
            prompt_rows.append(
                Tr(
                    Td(prompt['name'], cls="px-4 py-2"),
                    Td(prompt['created'], cls="px-4 py-2"),
                    Td(
                        Button("Edit", onclick=f"editPrompt('{prompt['id']}')", cls="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-8 px-3 py-1 text-xs mr-1"),
                        Button("Delete", onclick=f"deletePrompt('{prompt['id']}')", cls="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-8 px-3 py-1 text-xs"),
                        cls="px-4 py-2"
                    )
                )
            )
        
        content = [
            # Header with actions
            create_card(
                title="Prompt Management",
                content=Div(
                    P("Create and manage prompts for optimization", cls="text-muted-foreground mb-4"),
                    Div(
                        Button("Add Existing Prompt", onclick="showCreateForm('prompt')", id="create-prompt-btn", cls="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-8 px-3 py-1 text-xs mr-2"),
                        Button("Generate Prompt", onclick="showGenerateForm()", id="generate-prompt-btn", cls="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-secondary text-secondary-foreground hover:bg-secondary/90 h-8 px-3 py-1 text-xs mr-2"),
                        Button("Simple Optimizer", onclick="window.location.href='/simple-optimizer'", cls="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-8 px-3 py-1 text-xs"),
                        cls="flex gap-2"
                    )
                )
            ),
            
            # Create form (hidden)
            Div(
                create_card(
                    title="Create New Prompt",
                    content=Form(
                        Div(
                            Label("Prompt Name", cls="block text-sm font-medium mb-1"),
                            Input(type="text", name="name", required=True, cls="w-full p-2 border rounded mb-3")
                        ),
                        Div(
                            Label("System Prompt", cls="block text-sm font-medium mb-1"),
                            Textarea(name="system_prompt", rows="4", placeholder="System instructions for the AI", cls="w-full p-2 border rounded mb-3")
                        ),
                        Div(
                            Label("User Prompt", cls="block text-sm font-medium mb-1"),
                            Textarea(name="user_prompt", rows="4", placeholder="User prompt template (use {variables} for placeholders)", required=True, cls="w-full p-2 border rounded mb-3")
                        ),
                        Div(
                            Label("Description", cls="block text-sm font-medium mb-1"),
                            Textarea(name="description", rows="2", placeholder="Optional description", cls="w-full p-2 border rounded mb-3")
                        ),
                        Button("Create", type="submit", cls="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-8 px-3 py-1 text-xs mr-2"),
                        Button("Cancel", type="button", onclick="hideCreateForm('prompt')", cls="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-8 px-3 py-1 text-xs"),
                        method="post",
                        action="/prompts/create"
                    )
                ),
                id="create-prompt-form",
                cls="hidden mt-4"
            ),
            
            # Generate prompt form (hidden)
            Div(
                create_card(
                    title="Generate Prompt with AI",
                    content=Form(
                        Div(
                            Label("Describe what you want your prompt to do", cls="block text-sm font-medium mb-1"),
                            Textarea(name="description", rows="6", placeholder="Example: I want to create a prompt that analyzes customer support emails and categorizes them by urgency, sentiment, and issue type. The output should be in JSON format.", required=True, cls="w-full p-2 border rounded mb-3")
                        ),
                        Div(
                            Button("Generate", type="submit", cls="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-8 px-3 py-1 text-xs mr-2"),
                            Button("Cancel", type="button", onclick="hideGenerateForm()", cls="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-8 px-3 py-1 text-xs"),
                            cls="flex gap-2"
                        ),
                        method="post",
                        action="/prompts/generate"
                    )
                ),
                id="generate-prompt-form",
                cls="hidden mt-4"
            ),
            
            # Prompts table
            create_card(
                title="Your Prompts",
                content=Div(
                    Table(
                        Thead(
                            Tr(
                                Th("Name", cls="px-4 py-2 text-left"),
                                Th("Created", cls="px-4 py-2 text-left"),
                                Th("Actions", cls="px-4 py-2 text-left")
                            )
                        ),
                        Tbody(*prompt_rows),
                        cls="w-full border-collapse border border-gray-300"
                    ) if prompt_rows else P("No prompts found. Create your first prompt!", cls="text-gray-500 text-center py-8")
                )
            ),
            
            # JavaScript
            Script("""
                function showCreateForm(type) {
                    document.getElementById('create-' + type + '-form').classList.remove('hidden');
                    document.getElementById('create-' + type + '-btn').style.display = 'none';
                }
                
                function hideCreateForm(type) {
                    document.getElementById('create-' + type + '-form').classList.add('hidden');
                    document.getElementById('create-' + type + '-btn').style.display = 'inline-block';
                }
                
                function showGenerateForm() {
                    document.getElementById('generate-prompt-form').classList.remove('hidden');
                    document.getElementById('generate-prompt-btn').style.display = 'none';
                }
                
                function hideGenerateForm() {
                    document.getElementById('generate-prompt-form').classList.add('hidden');
                    document.getElementById('generate-prompt-btn').style.display = 'inline-block';
                }
                
                function editPrompt(id) {
                    window.location.href = '/prompts/' + id + '/edit';
                }
                
                async function deletePrompt(id) {
                    if (confirm('Are you sure you want to delete this prompt?')) {
                        try {
                            const response = await fetch('/prompts/' + id, {method: 'DELETE'});
                            if (response.ok) {
                                location.reload();
                            } else {
                                alert('Error deleting prompt');
                            }
                        } catch (error) {
                            alert('Error deleting prompt');
                        }
                    }
                }
            """)
        ]
        
        return create_main_layout(
            "Prompts",
            Div(*content),
            current_page="prompts"
        )

    @app.post("/prompts/create")
    async def create_prompt(request):
        """Create a new prompt"""
        try:
            form_data = await request.form()
            name = form_data.get('name', '').strip()
            system_prompt = form_data.get('system_prompt', '').strip()
            user_prompt = form_data.get('user_prompt', '').strip()
            description = form_data.get('description', '').strip()
            
            if not name or not user_prompt:
                return HTMLResponse('<script>alert("Please provide name and user prompt"); window.history.back();</script>')
            
            db = Database()
            prompt_id = db.create_prompt(
                name=name,
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            return HTMLResponse('<script>alert("Prompt created successfully!"); window.location.href="/prompts";</script>')
            
        except Exception as e:
            return HTMLResponse(f'<script>alert("Error creating prompt: {str(e)}"); window.history.back();</script>')

    @app.get("/prompts/{prompt_id}")
    async def get_prompt(request):
        """Get prompt details (API endpoint)"""
        prompt_id = request.path_params['prompt_id']
        
        try:
            db = Database()
            prompt = db.get_prompt(prompt_id)
            
            if not prompt:
                return {"success": False, "error": "Prompt not found"}
            
            return {"success": True, "prompt": prompt}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.get("/prompts/{prompt_id}/edit")
    async def edit_prompt_page(request):
        """Edit prompt page"""
        prompt_id = request.path_params['prompt_id']
        
        db = Database()
        prompt = db.get_prompt(prompt_id)
        
        if not prompt:
            return HTMLResponse('<script>alert("Prompt not found"); window.location.href="/prompts";</script>')
        
        # Extract variables from database structure
        variables = prompt.get('variables', {})
        system_prompt = variables.get('system_prompt', '')
        user_prompt = variables.get('user_prompt', '')
        
        content = [
            create_card(
                title=f"Edit Prompt: {prompt['name']}",
                content=Form(
                    Div(
                        Label("Prompt Name", cls="block text-sm font-medium mb-1"),
                        Input(type="text", name="name", value=prompt['name'], required=True, cls="w-full p-2 border rounded mb-3")
                    ),
                    Div(
                        Label("System Prompt", cls="block text-sm font-medium mb-1"),
                        Textarea(system_prompt, name="system_prompt", rows="4", cls="w-full p-2 border rounded mb-3")
                    ),
                    Div(
                        Label("User Prompt", cls="block text-sm font-medium mb-1"),
                        Textarea(user_prompt, name="user_prompt", rows="4", required=True, cls="w-full p-2 border rounded mb-3")
                    ),
                    Button("Update", type="submit", cls="px-4 py-2 bg-primary text-primary-foreground rounded mr-2"),
                    Button("Cancel", type="button", onclick="window.location.href='/prompts'", cls="px-4 py-2 border rounded"),
                    method="post",
                    action=f"/prompts/{prompt_id}/update"
                )
            )
        ]
        
        return create_main_layout(
            f"Edit Prompt: {prompt['name']}",
            Div(*content),
            current_page="prompts"
        )

    @app.post("/prompts/{prompt_id}/update")
    async def update_prompt(request):
        """Update a prompt"""
        prompt_id = request.path_params['prompt_id']
        
        try:
            form_data = await request.form()
            name = form_data.get('name', '').strip()
            system_prompt = form_data.get('system_prompt', '').strip()
            user_prompt = form_data.get('user_prompt', '').strip()
            
            if not name or not user_prompt:
                return HTMLResponse('<script>alert("Please provide name and user prompt"); window.history.back();</script>')
            
            db = Database()
            db.update_prompt(
                prompt_id=prompt_id,
                name=name,
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            return HTMLResponse('<script>alert("Prompt updated successfully!"); window.location.href="/prompts";</script>')
            
        except Exception as e:
            return HTMLResponse(f'<script>alert("Error updating prompt: {str(e)}"); window.history.back();</script>')

    @app.delete("/prompts/{prompt_id}")
    async def delete_prompt(request):
        """Delete a prompt"""
        prompt_id = request.path_params['prompt_id']
        
        try:
            db = Database()
            db.delete_prompt(prompt_id)
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.post("/prompts/generate")
    async def generate_prompt(request):
        """Generate a prompt using Nova best practices"""
        print("🔍 DEBUG - Generate prompt route hit")
        try:
            form_data = await request.form()
            description = form_data.get('description', '').strip()
            print(f"🔍 DEBUG - Description: {description[:100]}...")
            
            if not description:
                return HTMLResponse('<script>alert("Please provide a description"); window.history.back();</script>')
            
            # Import Nova template
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
            from amzn_nova_prompt_optimizer.core.optimizers.nova_meta_prompter.nova_prompt_template import NOVA_PROMPT_TEMPLATE
            
            # Create the generation prompt with specific variable format instructions
            variable_instructions = """
CRITICAL: When creating the user prompt, use variables in this exact format: {{ variable_name }}
For example: {{ input }}, {{ text }}, {{ content }}, etc.
DO NOT use [<VARIABLES>] or {variables} or any other format.
The user prompt MUST contain {{ input }} as the main variable for the input data.
"""
            
            generation_prompt = NOVA_PROMPT_TEMPLATE + variable_instructions + f"\n\nOriginal Prompt:\n{description}"
            
            print("🔍 DEBUG - About to call Nova API")
            
            # Use direct Bedrock call like simple_optimizer.py
            import boto3
            import json
            
            bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
            
            response = bedrock.invoke_model(
                modelId='us.amazon.nova-premier-v1:0',
                body=json.dumps({
                    "system": [{"text": "You are an expert prompt engineer. Follow the instructions exactly."}],
                    "messages": [{"role": "user", "content": [{"text": generation_prompt}]}],
                    "inferenceConfig": {"maxTokens": 2000, "temperature": 0.3}
                })
            )
            
            response_body = json.loads(response['body'].read())
            generated_content = response_body['output']['message']['content'][0]['text']
            print(f"🔍 DEBUG - Generated content length: {len(generated_content)}")
            
            # Parse system and user prompts from the response
            import re
            system_match = re.search(r'<system_prompt>(.*?)</system_prompt>', generated_content, re.DOTALL)
            user_match = re.search(r'<user_prompt>(.*?)</user_prompt>', generated_content, re.DOTALL)
            
            if not system_match or not user_match:
                print("🔍 DEBUG - Failed to parse prompts from response")
                return HTMLResponse('<script>alert("Failed to generate proper prompt format"); window.history.back();</script>')
            
            system_prompt = system_match.group(1).strip()
            user_prompt = user_match.group(1).strip()
            print(f"🔍 DEBUG - Parsed prompts successfully")
            
            # Escape HTML characters to prevent syntax errors
            import html
            system_prompt_escaped = html.escape(system_prompt)
            user_prompt_escaped = html.escape(user_prompt)
            
            # Show review page using FastHTML components
            from components.layout import create_main_layout, create_card
            
            content = [
                create_card(
                    title="Review Generated Prompt",
                    content=Form(
                        Div(
                            Label("Prompt Name", cls="block text-sm font-medium mb-1"),
                            Input(type="text", name="name", required=True, placeholder="Enter a name for this prompt", cls="w-full p-2 border rounded mb-3")
                        ),
                        Div(
                            Label("System Prompt", cls="block text-sm font-medium mb-1"),
                            Textarea(system_prompt, name="system_prompt", rows="8", cls="w-full p-2 border rounded mb-3")
                        ),
                        Div(
                            Label("User Prompt", cls="block text-sm font-medium mb-1"),
                            Textarea(user_prompt, name="user_prompt", rows="6", cls="w-full p-2 border rounded mb-3")
                        ),
                        Div(
                            Button("Save Prompt", type="submit", cls="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-8 px-3 py-1 text-xs mr-2"),
                            Button("Start Over", type="button", onclick="window.location.href='/prompts'", cls="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-8 px-3 py-1 text-xs"),
                            cls="flex gap-2"
                        ),
                        method="post",
                        action="/prompts/save-generated"
                    )
                )
            ]
            
            return create_main_layout(
                "Review Generated Prompt",
                Div(*content),
                current_page="prompts"
            )
            
        except Exception as e:
            print(f"❌ DEBUG - Error in generate_prompt: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            return HTMLResponse(f'<script>alert("Error generating prompt: {str(e)}"); window.history.back();</script>')

    @app.post("/prompts/save-generated")
    async def save_generated_prompt(request):
        """Save the generated prompt using existing create logic"""
        try:
            form_data = await request.form()
            name = form_data.get('name', '').strip()
            system_prompt = form_data.get('system_prompt', '').strip()
            user_prompt = form_data.get('user_prompt', '').strip()
            
            if not name or not user_prompt:
                return HTMLResponse('<script>alert("Please provide name and user prompt"); window.history.back();</script>')
            
            # Use the same database save logic as create_prompt
            db = Database()
            prompt_id = db.create_prompt(
                name=name,
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            return HTMLResponse('<script>alert("Prompt saved successfully!"); window.location.href="/prompts";</script>')
            
        except Exception as e:
            return HTMLResponse(f'<script>alert("Error saving prompt: {str(e)}"); window.history.back();</script>')
