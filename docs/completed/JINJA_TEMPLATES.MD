Here is the unified implementation plan. You can save this as a markdown file and provide it to `aider` to guide the refactoring process.

# Plan: Refactor Aider Prompt Generation to Handlebars 🚀

### 🎯 Objective

The goal is to refactor `aider`'s prompt generation by replacing Python f-string manipulation with a robust Handlebars templating system. This will decouple prompt content from application logic, making prompts easier to manage, test, and evolve.

-----

### ⚙️ Phase 1: Dependencies & Core Implementation

First, we'll set up the core components for templating.

#### 1.1. Add Dependency

The `pybars3` library is required. Add it to the project's dependencies.

```bash
pip install pybars3
```

#### 1.2. New Directory Structure

Create a new `prompts` directory alongside a new `render.py` module inside the `aider` package.

```
aider/
├── ... (existing aider files)
├── render.py        #<-- New: The central template renderer
└── prompts/         #<-- New: Directory for all .hbs files
    ├── system.hbs
    └── ... (other .hbs templates)
```

#### 1.3. Create the Renderer Module

This module provides a singleton `renderer` instance to manage all template operations.

**File to create: `aider/render.py`**

```python
import os
from pybars import Compiler

class Renderer:
    """
    A singleton class to discover, compile, and render Handlebars templates.
    """
    def __init__(self, template_dir="prompts"):
        self.compiler = Compiler()
        self.templates = self._load_templates(template_dir)
        self._register_helpers()

    def _load_templates(self, template_dir):
        """Loads all .hbs files from the specified directory."""
        templates = {}
        base_dir = os.path.dirname(os.path.abspath(__file__))
        prompts_path = os.path.join(base_dir, template_dir)
        
        if not os.path.isdir(prompts_path):
            raise FileNotFoundError(f"Template directory not found: {prompts_path}")

        for filename in os.listdir(prompts_path):
            if filename.endswith(".hbs"):
                name = filename[:-4] # Use filename without extension as template name
                with open(os.path.join(prompts_path, filename), "r", encoding="utf-8") as f:
                    templates[name] = self.compiler.compile(f.read())
        return templates
    
    def _register_helpers(self):
        """Registers custom Handlebars helpers for complex formatting."""
        # This is the place to add any needed helpers. For example:
        # def format_files_helper(this, files):
        #     # Logic to format a list of file objects
        #     return "\n".join([f"- {file.path}" for file in files])
        # self.compiler.register_helper("format_files", format_files_helper)
        pass

    def render(self, template_name: str, context: dict) -> str:
        """Renders a compiled template with the given context."""
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found.")
        return self.templates[template_name](context)

# Singleton instance for easy, consistent access across the project
renderer = Renderer()
```

-----

### 📝 Phase 2: Refactoring Strategy

The core strategy is to use the **"Context Builder" pattern**. For each prompt, a dedicated method will assemble all required data into a dictionary, which is then passed to the renderer.

#### 2.1. The Context Builder Pattern

Refactor methods in the `Coder` classes that currently build prompts.

**Pattern:**

1.  Create a dedicated `_build_<prompt_name>_context()` method.
2.  This method gathers all data from various sources (`self`, `RepoMap`, etc.).
3.  It returns a single, complete context dictionary.
4.  The original method then calls this builder and passes the result to `renderer.render()`.

**Conceptual Example (in a `Coder` class):**

```python
# Import the new renderer at the top of the file
from .render import renderer

# ... inside the Coder class

def _build_main_prompt_context(self) -> dict:
    """Gathers all data needed for the main prompt template."""
    repo_map_content = self.get_repo_map()
    
    # Assemble the complete context for this specific prompt
    context = {
        "repo_map": repo_map_content,
        "conversation_history": self.get_formatted_history(),
        "user_request": self.user_request,
        "has_git_diff": self.git_diff is not None,
        "git_diff": self.git_diff
    }
    return context

def render_main_prompt(self):
    """Refactored method to build and render the main prompt."""
    prompt_context = self._build_main_prompt_context()
    return renderer.render("main_prompt", prompt_context)
```

-----

### ✨ Phase 3: Template Authoring Best Practices

Follow these guidelines when creating the `.hbs` files in the `prompts/` directory.

#### 3.1. Handling Optional Content with `{{#if}}`

**Do not** rely on post-processing to remove unused variables. Use Handlebars' built-in logic to conditionally render sections of the prompt. This makes the templates robust and self-contained.

**Example `prompts/main_prompt.hbs`:**

```handlebars
{{! Use triple braces for raw content like code or diffs }}
{{{repo_map}}}

{{#if has_git_diff}}
Here is the git diff of the user's changes:
---
{{{git_diff}}}
---
{{/if}}

{{{conversation_history}}}

User request: {{user_request}}
```

#### 3.2. Reusing Content with Partials `{{> ...}}`

For common, reusable chunks of prompt text (like a file listing), create a partial template. Partial filenames should start with an underscore (e.g., `_file_list.hbs`).

**Example Partial `prompts/_repo_map_section.hbs`:**

```handlebars
{{#if repo_map}}
This is the current repository layout:
{{{repo_map}}}
{{/if}}
```

You can then include this in any other template using `{{> _repo_map_section}}`. This keeps your prompts DRY.
