# Design Draft: Full Refactor to Handlebars Templating

This document outlines a plan to completely replace the current class-based prompt construction system in `aider` with a template-first architecture powered by Handlebars.

### 🎯 Objective

The goal is to make `.hbs` template files the **single source of truth** for all prompt content and structure. This will fully decouple prompt engineering from Python application logic, eliminate the `*_prompts.py` class hierarchy, and create a more maintainable and transparent system.

---

### 1. The New Architecture: Template-First Design

The core principle is that the `aider/prompts/` directory becomes a comprehensive library of composable templates. The Python prompt classes (`CoderPrompts`, `EditBlockFencedPrompts`, etc.) will be removed entirely.

#### 1.1. The `prompts` Directory: A Library of Templates

The `aider/prompts/` directory will contain two types of files:

*   **Base Templates (`<format_name>.hbs`):** One for each primary edit format. These are the top-level templates that define the overall structure of a prompt.
    *   `diff-fenced.hbs`
    *   `whole-file.hbs`
    *   `pkm.hbs`
    *   `cbt.hbs`
    *   etc.

*   **Partials (`_*.hbs`):** Reusable components that replace the inherited attributes from the current `CoderPrompts` base class. These partials can be included in any base template.
    *   `_system_reminders.hbs`: Contains the rules for a given edit format.
    *   `_shell_command_reminders.hbs`: Contains the logic for suggesting shell commands.
    *   `_final_reminders.hbs`: Contains prompts like the `lazy_prompt` or `overeager_prompt`.
    *   `_file_listing.hbs`: A template for formatting files added to the chat.

A base template like `diff-fenced.hbs` would then be composed of these partials:

**Example: `aider/prompts/diff-fenced.hbs`**
```handlebars
{{! This is the main system prompt content }}
You are Aider, an AI pair programming assistant.

{{! Include the system reminder partial for this format }}
{{> _system_reminders}}

{{! Conditionally include shell command info }}
{{#if include_shell_commands}}
  {{> _shell_command_reminders}}
{{/if}}

{{! Include other reminders if they exist }}
{{#if final_reminders}}
  {{{final_reminders}}}
{{/if}}

---
{{! Now, the main content }}

{{{repo_map}}}

{{{read_only_files}}}

{{{chat_files}}}

{{{conversation_history}}}
```

#### 1.2. The `Coder` and the Central Context Builder

All logic for assembling prompt data will be centralized within the `Coder` class in `base_coder.py`. This removes logic from the deleted `*_prompts.py` files.

A new primary method, `_build_template_context()`, will be responsible for creating the *entire* context dictionary needed by any template. It will inspect the coder's state (`self.edit_format`, `self.pkm_mode`, `self.suggest_shell_commands`, etc.) to decide which data and boolean flags to set.

**Example `_build_template_context()` in `base_coder.py`:**
```python
def _build_template_context(self):
    """
    Builds a universal context dictionary for any Handlebars template.
    This method becomes the single source for all prompt data.
    """
    # This logic replaces EditorDiffFencedPrompts's behavior of blanking out prompts.
    is_editor_mode = self.edit_format.startswith("editor-")

    context = {
        "repo_map": self.get_repo_map(),
        "read_only_files": self.get_read_only_files_content(),
        "chat_files": self.get_files_content(),
        "conversation_history": self._get_formatted_conversation(),
        "fence": self.fence,
        "platform": self.get_platform_info(),

        # --- Boolean flags to control template sections ---
        "include_shell_commands": not is_editor_mode and self.suggest_shell_commands,
        "include_go_ahead_tip": not is_editor_mode,

        # --- Other conditional content ---
        "final_reminders": self._get_final_reminders_text(), # A helper to build this string
    }
    return context
```

#### 1.3. The Final Rendering Step

The `format_messages` method in `base_coder.py` will be greatly simplified. Its new job is to:
1.  Determine the correct template name from `self.edit_format`.
2.  Call the central context builder.
3.  Call the renderer to get the final prompt string.
4.  Wrap the string in a single "user" role message.

**Example `format_messages()` in `base_coder.py`:**
```python
def format_messages(self):
    # 1. Determine the template name
    template_name = self.edit_format.replace("editor-", "") # Example logic

    # 2. Build the universal context
    context = self._build_template_context()

    # 3. Render the final prompt
    prompt_content = self.renderer.render(template_name, context)

    # 4. Return the single, fully-formed prompt message
    chunks = ChatChunks()
    chunks.done = [dict(role="user", content=prompt_content)]
    return chunks
```

---

### 2. Before and After Comparison

| Aspect                | Current Architecture (Class-Based)                               | New Architecture (Handlebars-Based)                                    |
| :-------------------- | :--------------------------------------------------------------- | :--------------------------------------------------------------------- |
| **Prompt Source**     | Python classes in `aider/coders/*_prompts.py` files.             | `.hbs` files in the `aider/prompts/` directory.                        |
| **Reusability**       | Python class inheritance (`EditorDiff...` inherits from `EditBlock...`). | Handlebars partials (`{{> _partial_name}}`).                           |
| **Variations**        | Subclassing and overriding string attributes (e.g., `shell_cmd_prompt = ""`). | A single context builder setting boolean flags (`include_shell_commands: False`). |
| **Logic Location**    | Spread across multiple `*_prompts.py` files.                     | Centralized in `Coder._build_template_context()` in `base_coder.py`.   |
| **Files to Delete**   | All `aider/coders/*_prompts.py` files.                           | None (but many new `.hbs` files will be created).                      |
| **Data Flow**         | Complex `format_chat_chunks()` assembles many small messages.    | Simple `format_messages()` assembles one large prompt from a template. |

---

### 3. Pros and Cons of This Approach

#### Pros

*   **True Separation of Concerns:** The prompt text (the "view") is completely decoupled from the application logic. Prompt engineers can work on `.hbs` files without needing to understand Python inheritance.
*   **Reduced Boilerplate:** Eliminates numerous small Python files (`*_prompts.py`) in favor of a single directory of templates.
*   **Declarative and Readable:** The template logic (`{{#if ...}}`) is often more declarative and easier to grasp for simple conditional content than navigating Python class hierarchies.
*   **Centralized Logic:** All data-gathering logic is in one place (`_build_template_context`), making it easier to see what data is available to prompts.

#### Cons

*   **Major Refactoring Effort:** This is a high-risk, invasive change that touches the core of how `aider` communicates with the LLM. It cannot be done incrementally without significant temporary scaffolding.
*   **Complex Central Context Builder:** The `_build_template_context()` method could become a large, complex "god object" that knows about every possible variable for every template. This can make it hard to trace where a specific piece of data comes from.
*   **Loss of Static Analysis:** It becomes harder for IDEs and static analysis tools to determine which context keys are used by which templates, potentially leading to dead code in the context builder or unused variables.
*   **Testing Overhaul:** All existing tests that mock prompt attributes would need to be completely rewritten to mock the renderer or the context builder.
