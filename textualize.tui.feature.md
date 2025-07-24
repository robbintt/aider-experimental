# Aider Textual TUI Development Plan

## Project Context

Aider is an AI-powered command-line tool that functions as a pair programmer for developers. It allows users to chat with an AI that can read, write, and edit code directly within their local git repository. The current interface is a simple command-line REPL (Read-Eval-Print Loop).

This document outlines the plan to replace that REPL with a modern, rich Terminal User Interface (TUI) built using the [Textual](https://textual.textualize.io/) framework for Python. The new TUI aims to provide a more interactive, intuitive, and powerful user experience.

## Key Concepts

*   **Coder:** The core Aider class that manages the LLM, conversation history, file context, and application of code edits.
*   **In-Chat Files:** The set of files the user has explicitly added to the conversation for the AI to focus on.
*   **Repo Map:** A concise, high-level representation of the entire repository's structure, used to give the AI broader context beyond the in-chat files.
*   **Slash Commands:** Commands in the current CLI, like `/add` or `/test`, that will be replaced by interactive UI elements (buttons, menus, command palette) in the new TUI.

## Guiding Principles

1.  **Incremental Development:** Each task is small, self-contained, and delivers a specific piece of functionality.
2.  **Stability First:** After every task, all existing tests must pass. The application must be buildable and runnable.
3.  **Zero Impact on CLI:** The existing command-line interface (`aider`) will remain the default and must be completely unaffected by this development. All TUI code will live in a new file (`aider/tui.py`) and be activated by a new, dedicated flag (`--tui`).
4.  **Fly-the-Plane-While-Upgrading-It:** The TUI, even in its early stages, will be used to continue its own development.

---

## Phase 1: Minimum Viable Product (MVP)

**Goal:** Establish a functional, barebones TUI that can run a chat session with the AI and apply edits. This phase proves the core integration between Textual and the Aider `Coder`.

- [x] **Task 1.1: Create the TUI Entry Point**
*   **Action:** Modify `aider/main.py` to add a `--tui` command-line flag. When this flag is used, Aider will attempt to launch the TUI.
*   **Implementation:**
    1.  In `get_parser()` within `aider/args.py`, add a new argument: `parser.add_argument("--tui", action="store_true", help="Run the experimental Textual TUI.")`.
    2.  At the end of the `main()` function, right before the main `while True:` loop, add a block to handle the new flag:
        ```python
        if args.tui:
            # This will be replaced in the next task
            io.tool_output("TUI not yet implemented. Exiting.")
            return 0
        ```
*   **Verification:**
    *   Run the test suite. All tests must pass.
    *   Run `aider` (without the flag). It must launch the standard CLI.
    *   Run `aider --tui`. It should print the "not implemented" message and exit.

- [x] **Task 1.2: Implement the Basic TUI Application Shell**
*   **Action:** Create the `aider/tui.py` file and implement a basic Textual `App` that can be launched from `main.py`.
*   **Implementation:**
    1.  In `pyproject.toml`, add a `tui` optional dependency pointing to a new `requirements/requirements-tui.txt` file.
    2.  Create `requirements/requirements-tui.in` and `requirements/requirements-tui.txt`, with both containing `textual`.
    3.  Create a new file: `aider/tui.py`.
    4.  In `aider/tui.py`, define a minimal Textual app:
        ```python
        from textual.app import App, ComposeResult
        from textual.widgets import Header, Footer

        class TuiApp(App):
            """Aider's Textual TUI."""

            BINDINGS = [("q", "quit", "Quit")]

            def compose(self) -> ComposeResult:
                yield Header()
                yield Footer()

        def run_tui(args):
            app = TuiApp()
            app.run()
        ```
    5.  In `aider/main.py`, modify the `if args.tui:` block to import and call the TUI runner. This import must be local to the `if` block to avoid impacting CLI startup time.
        ```python
        if args.tui:
            try:
                from aider.tui import run_tui
                run_tui(args)
            except ImportError:
                io.tool_error("Please install the Textual dependencies to run the TUI:")
                io.tool_error("pip install 'aider-chat[tui]'")
            return 0
        ```
*   **Verification:**
    *   Run the test suite. All tests must pass.
    *   Run `aider --tui`. It should launch a blank Textual application with a header and footer. Pressing 'q' should exit.

- [x] **Task 1.3: Integrate the Aider Coder and Chat UI**
*   **Action:** Instantiate the Aider `Coder` within the TUI and create a basic chat interface consisting of a log and an input box.
*   **Implementation:**
    1.  In `aider/tui.py`, modify `TuiApp` to initialize the `Coder` on mount. Use the `main(return_coder=True)` function to reuse the existing setup logic from the CLI.
    2.  Implement a `RichLog` for conversation history and an `Input` for user prompts.
    3.  The `Coder` must be run in a background `Worker` to prevent blocking the UI.
        ```python
        # In aider/tui.py
        import asyncio
        import sys
        from textual.widgets import RichLog, Input

        # ... inside TuiApp class ...
        def __init__(self, args):
            self.args = args
            self.coder = None
            super().__init__()

        def on_mount(self) -> None:
            """Called when app starts."""
            # Use a worker to avoid blocking the UI during Coder setup
            self.run_worker(self.run_coder_setup)

        async def run_coder_setup(self) -> None:
            """Setup the Coder in the background."""
            from aider.main import main as main_runner

            # Pass all args except the script name itself
            self.coder = await asyncio.to_thread(
                main_runner, self.args, return_coder=True
            )
            # You might want to post a message to the UI thread
            # to enable the input once the coder is ready.
        
        def compose(self) -> ComposeResult:
            yield Header()
            yield RichLog(wrap=True, id="chat_log")
            yield Input(placeholder="Enter your prompt...", id="prompt_input")
            yield Footer()
        ```
*   **Verification:**
    *   Run the test suite. All tests must pass.
    *   Run `aider --tui`. The app should launch, and after a moment (while the coder loads), it should be ready for input.

- [x] **Task 1.4: Implement the Core Chat Loop**
*   **Action:** Wire up the input box to send the user's prompt to the `Coder` worker and stream the response back to the `RichLog`.
*   **Implementation:**
    1.  Define new `Message` classes for chat updates: `UpdateChatLog`, `ShowDiff`, and `ChatTaskDone`.
    2.  Implement the `on_input_submitted` handler. It should disable and clear the `Input`, then call `self.run_worker` to execute the main chat logic in the background.
    3.  Create an `async` worker method `run_chat_task(prompt)`. This method will use `asyncio.to_thread` to execute a synchronous, blocking helper method `_blocking_chat_runner(prompt)`. This prevents the chat processing from freezing the UI.
    4.  The `_blocking_chat_runner` will:
        *   Iterate through `self.coder.run_stream(prompt)`.
        *   For each chunk of the AI's response, use `self.post_message` to send an `UpdateChatLog` message.
        *   After the stream, check `self.coder.last_aider_commit_diff` and, if a diff exists, send a `ShowDiff` message.
        *   Finally, send a `ChatTaskDone` message.
    5.  Implement message handlers (`on_update_chat_log`, `on_show_diff`, `on_chat_task_done`) to process the messages posted from the worker. These handlers will update the `RichLog` and re-enable the `Input` widget.
*   **Verification:**
    *   Run `aider --tui`. The TUI should start without any files in chat.
    *   In the input box, type `/add <path_to_a_file>` and press Enter. The file should be added to the chat context.
    *   Enter a prompt like "add a comment to the top of the file".
    *   The AI's response should stream into the log.
    *   A diff of the change should be displayed in the log.
    *   The file on disk should be updated.
    *   The input box should be disabled during processing and re-enabled afterward.
    *   Alternatively, run `aider --tui <path_to_a_file>` and verify that making an edit works as described above.

- [x] **Task 1.4.1: Fix Chat Interaction and Feedback**
*   **Action:** User is unable to see typed text in the input box, and slash commands provide no feedback. The input becomes unresponsive after the first command.
*   **Implementation:**
    1.  In `_blocking_chat_runner`, redirect `sys.stdout` to an in-memory `io.StringIO()` buffer for the duration of the `coder` call. This captures all output from the `coder`'s `io` methods, which would otherwise corrupt the Textual display.
    2.  After the `coder` call completes, post the captured output to the chat log.
    3.  Wrap the chat logic in a `try...finally` block to ensure `sys.stdout` is always restored and the `ChatTaskDone` message is always posted, which prevents the UI from becoming unresponsive.
*   **Verification:**
    *   Text typed in the input box is now visible.
    *   Executing a slash command like `/add <file>` displays a confirmation message in the chat log.
    *   The input box remains active and usable after each command.

- [x] **Task 1.4.2: Fix AttributeError for diff attributes**
*   **Action:** The TUI crashes with an `AttributeError` because `last_aider_commit_diff` is not always present on the `coder` object. The `Undo` button was also broken.
*   **Implementation:** In `_blocking_chat_runner`, use `getattr` to safely access `last_aider_commit_diff` and `last_aider_commit_message` from the `coder` object. The call to `cmd_undo` was also corrected to be on the `coder` object.
*   **Verification:** The TUI no longer crashes after a change is made by the AI. Diffs are correctly displayed. The "Undo" button works.

- [x] **Task 1.4.3: Fix TUI display issues**
*   **Action:** User input text is invisible, and AI responses are displayed with one character per line.
*   **Implementation:**
    1.  Explicitly set the text `color` for the `#prompt_input` widget in CSS to ensure visibility against any background.
    2.  Replace the main chat `RichLog` with a `TextArea` widget. `RichLog` is line-oriented and not suitable for streaming character-by-character updates. `TextArea` supports continuous text insertion.
*   **Verification:**
    *   Text typed in the input box is visible.
    *   AI responses stream into the chat view correctly as a single block of text.

- [x] **Task 1.4.4: Fix `TextArea` method and input visibility**
*   **Action:** TUI crashes with `AttributeError` when updating the chat log, and input text is invisible.
*   **Implementation:**
    1.  Corrected the method for appending text to the `TextArea` to `textarea.insert_text()`.
    2.  Made the CSS selector for the prompt input more specific (`Input#prompt_input`) and set a `background` color to ensure it contrasts with the text color.
*   **Verification:**
    *   The application no longer crashes when the AI sends a response.
    *   Text typed in the input box is visible in both light and dark modes.

- [x] **Task 1.4.5: Fix `TextArea` method, input visibility, and command feedback**
*   **Action:** TUI crashes on text insertion, input text is invisible, and commands run from the UI provide no feedback.
*   **Implementation:**
    1.  Fixed the method for appending text to the `TextArea` to use the correct `insert()` method name and move the cursor to the end of the document first.
    2.  Updated the CSS for the `Input` widget to use Textual's theme variables (`$text`, `$surface`) which adapt to light/dark mode. Replaced the debug border with a standard `:focus` border.
    3.  Wrapped all blocking calls to `coder.commands` with `sys.stdout` redirection to capture and display their output in the chat log, providing consistent feedback for all UI actions.
*   **Verification:**
    *   The application no longer crashes when updating the chat log.
    *   Text typed in the input box is now clearly visible.
    *   Clicking files in the file browser and using commands from the palette now show output in the chat log.

- [x] **Task 1.4.6: Fix invisible input text by correcting theme conflict**
*   **Action:** Text typed into the `Input` widget is invisible.
*   **Implementation:**
    1.  Added a `Screen` style rule to the main CSS to establish a solid base `background` and `color` for the entire application, ensuring that theme variables (`$surface`, `$text`) are reliable.
    2.  Re-applied explicit `background` and `color` styles to the `Input` widget using these theme variables to guarantee contrast.
*   **Verification:** Text typed into the input field is now visible.

- [x] **Task 1.4.7: Fix invisible input text by isolating widget composition**
*   **Action:** The text echoing in the `Input` widget is not working. This may be an unforeseen interaction with the `TextArea.code_editor` widget.
*   **Implementation:** Replace the `TextArea.code_editor()` convenience method with a standard `TextArea()` widget, manually configured for the chat log. This eliminates a potential source of complex, conflicting styles that may be interfering with the `Input` widget's rendering.
*   **Verification:** Text typed into the input field is now visible as it is typed.

- [x] **Task 1.4.8: Fix `LanguageDoesNotExist` crash on startup**
*   **Action:** The TUI crashes on startup because the `tree-sitter` grammar for `markdown` is not installed.
*   **Implementation:** Remove the `language="markdown"` argument from the `TextArea` widget used for the chat log. This prevents the crash by allowing the widget to default to plain text rendering, which doesn't require a special grammar.
*   **Verification:** The TUI starts successfully without crashing.

- [x] **Task 1.4.9: Fix invisible input text by protecting `sys.stdout`**
*   **Action:** Text typed into the `Input` widget is not echoed to the screen. This is likely caused by the `coder` setup process permanently redirecting `sys.stdout`.
*   **Implementation:** In `run_coder_setup`, wrap the call to `main_runner` in a `try...finally` block to ensure that `sys.stdout` and `sys.stdin` are always restored after the `coder` is initialized. This guarantees that Textual's renderer can always write to the correct output stream.
*   **Verification:** Text typed into the input field is visible as it is typed.

---

## Phase 2: Interactive Context and UI Fundamentals

**Goal:** Introduce the core interactive elements that provide a superior experience to the CLI.

- [x] **Task 2.1: Implement the Main UI Layout**
*   **Action:** Refactor the `compose` method to create a three-pane layout: a sidebar for controls, a main area for the chat, and a footer for key bindings.
*   **Implementation:** Use Textual's `Container` widgets with `dock` styling.
*   **Verification:** The TUI should now display distinct regions for the sidebar and main content, even if the sidebar is empty.

- [x] **Task 2.2: Add an Interactive File Browser**
*   **Action:** Add a `DirectoryTree` widget to the sidebar.
*   **Implementation:**
    1.  Populate the `DirectoryTree` with the contents of the current git repository.
    2.  Implement the `on_directory_tree_file_selected` handler.
    3.  In the handler, call `self.coder.add_rel_fname(path)` or `self.coder.drop_rel_fname(path)` to dynamically update the chat context.
    4.  Print a confirmation message to the chat log (e.g., "Added `file.py` to the chat.").
*   **Verification:** The user can now see the file tree and add/remove files from the chat context by clicking on them.

- [x] **Task 2.3: Improve Chat Display**
*   **Action:** Enhance the chat log to be cleaner and more informative.
*   **Implementation:**
    1.  When a diff is generated, display it inside a `Collapsible` widget. The title of the collapsible should be the commit message.
    2.  Add a simple "Undo" `Button` next to the `Collapsible` diff summary. When clicked, it should execute `self.coder.cmd_undo()`.
*   **Verification:** Diffs are now hidden by default, making the chat log easier to read. The user can undo the last change with a single click.

---

## Phase 3: Full Feature Parity

**Goal:** Achieve full parity with the existing CLI's capabilities, making the TUI a complete replacement.

- [x] **Task 3.1: Implement the Command Palette**
*   **Action:** Add a global `CommandPalette` and migrate the most common slash commands to it.
*   **Implementation:**
    1.  Define a custom `CommandProvider`.
    2.  Add commands for "Commit", "Test", "Lint", and "Clear Chat History".
    3.  These commands will call the corresponding methods on the `coder.commands` object (e.g., `self.coder.commands.cmd_commit()`).
*   **Verification:** The user can press `Ctrl+P` (or the configured key) to open the palette and execute core commands without typing them.

- [x] **Task 3.1.1: Fix TUI startup**
*   **Action:** The TUI is hanging on startup, showing a blank screen.
*   **Implementation:** The custom message handlers (`on_coder_ready`, etc.) are not being called. Decorate them with the `@on(...)` decorator to ensure they are registered correctly.
*   **Verification:** The TUI starts correctly, and the input prompt becomes active after the coder has loaded.

- [x] **Task 3.2: Create the Settings Tab**
*   **Action:** Implement a `TabbedContent` widget in the main panel with two tabs: "Chat" and "Settings".
*   **Implementation:**
    1.  Move the existing chat UI into the "Chat" tab.
    2.  Create a "Settings" tab with widgets (`Switch`, `Select`, `Input`) to control Aider's most important runtime settings (e.g., `auto-commits`, `model`, `test-cmd`).
    3.  Changes in the settings UI should dynamically update the `self.coder` object's configuration.
*   **Verification:** The user can switch to the settings tab and change Aider's behavior without restarting the application.

---

## Phase 4: Polish and Refinements

**Goal:** Refine the user experience and add high-value features not present in the original CLI.

- [x] **Task 4.1: Add a Repo Map Tab**
*   **Action:** Add a third tab to the main panel for the "Repo Map".
*   **Implementation:** When this tab is selected, it should call `self.coder.get_repo_map()` and display the result in a `RichLog` or `Markdown` widget.
*   **Verification:** The user can easily view the repository map from within the TUI.

- [ ] **Task 4.2: Implement Web Scraper UI**
*   **Action:** Add an `Input` and `Button` to the sidebar for scraping web content.
*   **Implementation:** When the button is clicked, the URL from the input is scraped in a background worker, and the content is added to the chat.
*   **Verification:** The user can add context from a web page directly through the UI.

- [ ] **Task 4.3: Add Status Bar and Notifications**
*   **Action:** Enhance the `Footer` to act as a status bar and add `Toast` notifications.
*   **Implementation:**
    1.  Display the current model, git branch, and status (e.g., "Thinking...") in the footer.
    2.  Use `self.app.notify("Message")` to provide non-blocking feedback for actions like "Commit successful" or "File added".
*   **Verification:** The TUI provides more ambient information and feedback, making the user experience smoother.

---

## Post-Phase 4: Future Enhancements

**Goal:** Explore new features that were never part of the original CLI design.

- [ ] **Task 5.1:** Advanced history browser for searching and reusing prompts from past sessions.
- [ ] **Task 5.2:** In-app theme editor for full visual customization.
- [ ] **Task 5.3:** Integration with other developer tools.

---

## References

*   [Textual Input Widget](https://textual.textualize.io/widgets/input/)
*   [Textual Styles Guide](https://textual.textualize.io/guide/styles/)
*   [Textual CSS Guide](https://textual.textualize.io/guide/CSS/)
*   [Textual Styles Reference](https://textual.textualize.io/styles/)
