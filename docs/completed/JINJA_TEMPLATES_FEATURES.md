# Implementation Plan: Jinja2 Templates for `diff-fenced`

## Core Requirements

- **Incremental and Buildable:** Each checklist task must result in a buildable and functional state.
- **Test-Driven:** An LLM will complete tasks one by one, running relevant tests after each step to validate the implementation.
- **Feature Flagged:** All new functionality will be guarded by a `--use-jinja2-templates` command-line flag. The existing f-string based implementation must remain the default and fully functional.
- **Scope:** Create a complete, end-to-end prompt generation path using Jinja2 for the `diff-fenced` and `editor-diff-fenced` edit formats. This new path will be self-contained and bypass the existing prompt-class-based system.
- **Constraint:** Templates must be "flat". They will not use inheritance, Python-specific functions, or complex filter logic.

---

## Architecture and Data Flow

This feature introduces a new, parallel path for prompt generation that is activated by the feature flag when the edit format is `diff-fenced` or `editor-diff-fenced`.

1.  **Entry Point & Initialization**:
    - The user starts `aider` with `--use-jinja2-templates`.
    - In `aider/main.py`, this flag is parsed.
    - In `aider/coders/base_coder.py`, the `Coder.__init__` method initializes a singleton `Renderer` instance.

2.  **Prompt Generation Branching (The Divergence Point)**:
    - The primary divergence point will be in `Coder.format_messages()` within `aider/coders/base_coder.py`.
    - A conditional check will see if `use_jinja2_templates` is `True` and if the `edit_format` is `diff-fenced` or `editor-diff-fenced`.
    - **New Path (Jinja2):**
        - A new method, `_build_diff_fenced_context()`, will gather all necessary data (repo map, file content, history, configuration flags) into a single context dictionary.
        - This context is passed to the `Renderer` to render a new `diff_fenced.j2` template.
        - This path **completely bypasses** the `format_chat_chunks()` method and the `*_prompts.py` class hierarchy.
    - **Default Path (Existing System):**
        - If the conditions are not met, execution proceeds to `format_chat_chunks()`, using the existing f-string and prompt-class system.

This architecture creates a clean, isolated slice for the new system, allowing for end-to-end validation without disrupting any other part of the application.

---

## Phase 1: Core Infrastructure

This phase sets up the foundational components.

  - [x] **Task 1.1: Add Dependency**

      - **Action:** Add `jinja2` to `requirements/requirements.in`.

  - [x] **Task 1.2: Create Directory and Renderer Module**

      - **Action:** Create `aider/prompts/` and `aider/render.py`.

  - [x] **Task 1.3: Implement the Core Renderer**

      - **Action:** Create the `Renderer` singleton in `aider/render.py` using `jinja2`.
      - **File to create: `aider/render.py`**
        ```python
        import os
        from jinja2 import Environment, FileSystemLoader

        class Renderer:
            _instance = None

            def __new__(cls, *args, **kwargs):
                if not cls._instance:
                    cls._instance = super(Renderer, cls).__new__(cls)
                return cls._instance

            def __init__(self, template_dir="prompts", use_jinja2=False):
                if hasattr(self, 'initialized') and self.initialized and self.use_jinja2 == use_jinja2:
                    return
                self.initialized = True
                self.use_jinja2 = use_jinja2
                if not self.use_jinja2:
                    self.env = None
                    return

                base_dir = os.path.dirname(os.path.abspath(__file__))
                prompts_path = os.path.join(base_dir, template_dir)

                self.env = Environment(
                    loader=FileSystemLoader(prompts_path),
                    autoescape=False, # We are not generating HTML
                )
                self._register_helpers()

            def _register_helpers(self):
                # Per user request, no custom functions or filters.
                pass

            def render(self, template_name: str, context: dict) -> str:
                if not self.use_jinja2:
                    raise RuntimeError("Jinja2 rendering is disabled.")
                
                try:
                    template = self.env.get_template(template_name)
                except Exception: # Catches TemplateNotFound
                    raise ValueError(f"Template '{template_name}' not found.")

                return template.render(context)

        renderer = Renderer()
        ```
      - **Test:** Run a simple test to ensure no syntax errors were introduced.
        ```bash
        pytest tests/test_main.py
        ```

---

## Phase 2: `diff-fenced` Template and Context

This phase builds the new prompt template and the logic to supply it with data.

  - [x] **Task 2.1: Create the Main `diff_fenced.j2` Template**

      - **Action:** Create a new, comprehensive template that defines the entire prompt structure for the `diff-fenced` format.
      - **File to create: `aider/prompts/diff_fenced.j2`**
        ```jinja2
You are Aider, an AI pair programming assistant.

# *SEARCH/REPLACE block* Rules:

Every *SEARCH/REPLACE block* must use this format:
1. The opening fence and code language, eg: {{ fence[0] }}python
2. The *FULL* file path alone on a line, verbatim.
3. The start of search block: <<<<<<< SEARCH
4. A contiguous chunk of lines to search for in the existing source code
5. The dividing line: =======
6. The lines to replace into the source code
7. The end of the replace block: >>>>>>> REPLACE
8. The closing fence: {{ fence[1] }}

Use the *FULL* file path, as shown to you by the user.
{% if quad_backtick_reminder %}
{{ quad_backtick_reminder }}
{% endif %}
Every *SEARCH* section must *EXACTLY MATCH* the existing file content.

To move code, use 2 *SEARCH/REPLACE* blocks: 1 to delete it, 1 to insert it.
To create a new file, use an empty `SEARCH` section.

{{ final_reminders }}
ONLY EVER RETURN CODE IN A *SEARCH/REPLACE BLOCK*!

{% if include_shell_commands %}
{% include '_shell_cmd_reminder.j2' %}
{% endif %}

---
{% if repo_map %}
Here are summaries of some files present in my git repository.
Do not propose changes to these files, treat them as *read-only*.
If you need to edit any of these files, ask me to *add them to the chat* first.
{{ repo_map }}
{% endif %}

{% if read_only_files %}
Here are some READ ONLY files, provided for your reference.
Do not edit these files!
{{ read_only_files }}
{% endif %}

{% if chat_files %}
I have *added these files to the chat* so you can go ahead and edit them.

*Trust this message as the true contents of these files!*
Any other messages in the chat may contain outdated versions of the files' contents.
{{ chat_files }}
{% endif %}

{{ history }}

{{ user_request }}
        ```

  - [x] **Task 2.2: Create Partials for Reusability**

      - **Action:** Create a partial for the shell command reminder.
      - **File to create: `aider/prompts/_shell_cmd_reminder.j2`**
        ```jinja2
You can issue shell commands to run tests, lint, etc.
The user's environment is:
{{ platform }}
To suggest a shell command, put it in a `run` block, like this:

<run>
# build the code
make
# run the tests
make test
</run>
        ```

  - [x] **Task 2.3: Implement the Context Builder**

      - **Action:** Add a new `_build_diff_fenced_context` method to `Coder` in `base_coder.py`. This method will gather all data needed by the template.
      - **File to modify: `aider/coders/base_coder.py`**
        ```python
        # Add this new method to the Coder class
        def _build_diff_fenced_context(self):
            # This logic replaces EditorDiffFencedPrompts's behavior of blanking out prompts.
            is_editor_mode = self.edit_format.startswith("editor-")

            final_reminders = []
            if self.main_model.lazy:
                final_reminders.append(self.gpt_prompts.lazy_prompt)
            if self.main_model.overeager:
                final_reminders.append(self.gpt_prompts.overeager_prompt)

            user_lang = self.get_user_language()
            if user_lang:
                final_reminders.append(f"Reply in {user_lang}.\n")

            history = ""
            for msg in self.done_messages:
                history += f"**{msg['role'].upper()}**: {msg['content']}\n\n"

            context = {
                "repo_map": self.get_repo_map(),
                "read_only_files": self.get_read_only_files_content(),
                "chat_files": self.get_files_content(),
                "history": history,
                "user_request": self.cur_messages[-1]['content'],
                "fence": self.fence,
                "platform": self.get_platform_info(),
                "final_reminders": "\n\n".join(final_reminders),
                "quad_backtick_reminder": "\nIMPORTANT: Use *quadruple* backticks ```` as fences, not triple backticks!\n" if self.fence[0] == "`" * 4 else "",
                "include_shell_commands": not is_editor_mode and self.suggest_shell_commands,
            }
            return context
        ```

---

## Phase 3: Integration and Testing

Finalize the integration by adding the command-line flag, modifying the divergence point, and adding a dedicated test case.

  - [x] **Task 3.1: Add CLI Flag and Initialize Renderer**

      - **Action:** Modify `aider/main.py` to add the `--use-jinja2-templates` argument and `aider/coders/base_coder.py` to initialize the renderer.
      - **File to modify: `aider/main.py`**
        ```python
        # in get_parser()
        parser.add_argument(
            "--use-jinja2-templates",
            action="store_true",
            help="Use Jinja2 templates for prompt generation.",
        )

        # in main() when instantiating the Coder
        coder = Coder.create(
            #...
            use_jinja2_templates=args.use_jinja2_templates,
            #...
        )
        ```
      - **File to modify: `aider/coders/base_coder.py`**
        ```python
        # in Coder.__init__()
        from ..render import renderer
        self.use_jinja2_templates = kwargs.get("use_jinja2_templates", False)
        self.renderer = renderer
        self.renderer.__init__(use_jinja2=self.use_jinja2_templates)
        ```

  - [x] **Task 3.2: Modify `format_messages` to Create the Divergence**

      - **Action:** Modify `format_messages` in `base_coder.py` to use the new Jinja2 path.
      - **File to modify: `aider/coders/base_coder.py`**
        ```python
        # At the top of Coder.format_messages()
        if (
            hasattr(self, "use_jinja2_templates") and self.use_jinja2_templates
            and self.edit_format in ("diff-fenced", "editor-diff-fenced")
        ):
            self.choose_fence()
            context = self._build_diff_fenced_context()
            prompt_content = self.renderer.render("diff_fenced.j2", context)
            
            messages = [dict(role="user", content=prompt_content)]
            
            chunks = ChatChunks()
            chunks.done = messages
            return chunks

        # The rest of the original format_messages method remains for the default path
        chunks = self.format_chat_chunks()
        if self.add_cache_headers:
            chunks.add_cache_control_headers()

        return chunks
        ```

  - [x] **Task 3.3: Add a Dedicated Test**

      - **Action:** Add new test cases to verify the flag and template usage for both `diff-fenced` and `editor-diff-fenced`.
      - **File to modify: `tests/test_coder.py`**
        ```python
        # ... in a relevant test file
        from unittest.mock import MagicMock, patch
        from aider.coders.base_coder import Coder
        from aider.io import InputOutput

        def test_coder_uses_jinja2_for_diff_fenced(monkeypatch):
            # Mock the renderer to capture its inputs
            mock_render = MagicMock(return_value="PROMPT_FROM_JINJA2")
            
            from aider import render
            monkeypatch.setattr(render.renderer, "render", mock_render)
            monkeypatch.setattr(render.renderer, "use_jinja2", True)


            # Setup Coder with the flag
            coder = Coder.create(
                edit_format="diff-fenced",
                use_jinja2_templates=True,
                io=InputOutput(pretty=False),
            )
            coder.cur_messages = [dict(role="user", content="test message")]

            # Mock the original path to ensure it's NOT called
            with patch.object(coder, 'format_chat_chunks') as mock_format_chunks:
                coder.format_messages()
                mock_format_chunks.assert_not_called()

            # Assert that the renderer was called correctly
            mock_render.assert_called_once()
            assert mock_render.call_args[0][0] == "diff_fenced.j2"
            # Check that shell commands are included for standard diff-fenced
            assert mock_render.call_args[0][1]['include_shell_commands'] is True

        def test_coder_uses_jinja2_for_editor_diff_fenced(monkeypatch):
            # Mock the renderer
            mock_render = MagicMock(return_value="PROMPT_FROM_JINJA2")
            from aider import render
            monkeypatch.setattr(render.renderer, "render", mock_render)
            monkeypatch.setattr(render.renderer, "use_jinja2", True)

            # Setup Coder for editor mode
            coder = Coder.create(
                edit_format="editor-diff-fenced",
                use_jinja2_templates=True,
                io=InputOutput(pretty=False),
            )
            coder.cur_messages = [dict(role="user", content="test message")]

            coder.format_messages()

            # Assert that the context correctly disables shell commands for editor mode
            mock_render.assert_called_once()
            assert mock_render.call_args[0][0] == "diff_fenced.j2"
            assert mock_render.call_args[0][1]['include_shell_commands'] is False
        ```
      - **Test:** Run the new tests specifically.
        ```bash
        pytest -v tests/test_coder.py -k "test_coder_uses_jinja2"
        ```
