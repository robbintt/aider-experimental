import asyncio
import io
import os
import sys

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.widgets import Button, Collapsible, DirectoryTree, Header, Footer, Input, RichLog


class TtyStringIO(io.StringIO):
    """A StringIO that has a `isatty` method."""

    def isatty(self) -> bool:
        return False


class TuiApp(App):
    """Aider's Textual TUI."""

    CSS = """
    #sidebar {
        dock: left;
        width: 40;
        overflow: auto;
    }
    #chat-container {
        overflow: auto;
    }
    .diff-container {
        height: auto;
    }
    .diff-container Collapsible {
        width: 1fr;
    }
    .diff-container Button {
        width: 10;
        height: 1;
        margin: 0 1;
    }
    """

    class CoderReady(Message):
        """Posted when the Coder is ready."""

    class UpdateChatLog(Message):
        """Posted to update the chat log with a new chunk of text."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class ShowDiff(Message):
        """Posted to show a diff in the chat log."""

        def __init__(self, diff: str, commit_message: str) -> None:
            super().__init__()
            self.diff = diff
            self.commit_message = commit_message

    class ChatTaskDone(Message):
        """Posted when a chat task is done."""

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, args):
        self.args = args
        self.coder = None
        super().__init__()

    def on_mount(self) -> None:
        """Called when app starts."""
        self.log("TUI mounted.")
        # Use a worker to avoid blocking the UI during Coder setup
        self.run_worker(self.run_coder_setup)

    async def run_coder_setup(self) -> None:
        """Setup the Coder in the background."""
        from aider.main import main as main_runner

        self.log("Starting Coder setup...")

        # Filter out --tui from sys.argv to prevent recursion
        tui_args = [arg for arg in sys.argv[1:] if arg != "--tui"]
        tui_args.append("--no-fancy-input")

        try:
            # main_runner is a synchronous function that does all the setup.
            # We run it in a thread to avoid blocking the UI.
            # It expects a list of command-line arguments (argv).
            #
            # We redirect stdin and stdout to in-memory streams to prevent
            # the Coder's setup process from interfering with the TUI's
            # control over the terminal.
            input_stream = TtyStringIO()
            output_stream = TtyStringIO()

            self.coder = await asyncio.to_thread(
                main_runner,
                tui_args,
                input=input_stream,
                output=output_stream,
                return_coder=True,
            )
            self.log("Coder setup finished.")

            # Log any output from the setup process for debugging
            setup_output = output_stream.getvalue()
            if setup_output:
                self.log("--- Coder Setup Output ---")
                self.log(setup_output)
                self.log("--------------------------")

            self.post_message(self.CoderReady())
            self.log("Posted CoderReady message.")
        except BaseException as e:
            self.log(f"Error during Coder setup: {e}")
            # Also post to the chat log so the user can see it
            self.post_message(self.UpdateChatLog(f"Error during Coder setup: {e}"))

    def on_coder_ready(self, message: "TuiApp.CoderReady") -> None:
        """Enable the prompt input when the coder is ready."""
        self.log("Coder is ready.")
        prompt_input = self.query_one("#prompt_input", Input)
        prompt_input.disabled = False
        prompt_input.focus()
        prompt_input.placeholder = "Enter your prompt..."

        sidebar = self.query_one("#sidebar")
        dir_tree = DirectoryTree(self.coder.root, id="file_browser")
        sidebar.mount(dir_tree)

    def on_update_chat_log(self, message: "TuiApp.UpdateChatLog") -> None:
        """Update the chat log with a new message."""
        self.query_one("#chat_log", RichLog).write(message.text)

    def on_show_diff(self, message: "TuiApp.ShowDiff") -> None:
        """Show a diff in the chat log."""
        chat_container = self.query_one("#chat-container")

        diff_log = RichLog(wrap=True, highlight=True)
        diff_log.write(f"```diff\n{message.diff}\n```")

        collapsible = Collapsible(
            diff_log,
            title=message.commit_message,
            collapsed=True,
        )

        undo_button = Button("Undo", name="undo")

        container = Horizontal(collapsible, undo_button, classes="diff-container")
        chat_container.mount(container, before="#prompt_input")

    def on_chat_task_done(self, message: "TuiApp.ChatTaskDone") -> None:
        """Re-enable the prompt input when a chat task is done."""
        prompt_input = self.query_one("#prompt_input", Input)
        prompt_input.disabled = False
        prompt_input.focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.name == "undo":
            # The button's parent is the Horizontal container
            container = event.button.parent
            event.button.disabled = True
            self.run_worker(self.run_undo(container), exclusive=False)

    async def run_undo(self, container_to_remove) -> None:
        """Run the undo command."""
        await asyncio.to_thread(self.coder.cmd_undo)
        self.post_message(self.UpdateChatLog("Undo complete."))
        await container_to_remove.remove()

    async def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Called when a file is selected in the directory tree."""
        event.stop()
        file_path = str(event.path)
        self.run_worker(self.handle_file_selected(file_path), exclusive=False)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle the user submitting a prompt."""
        prompt = event.value
        if not prompt:
            return

        prompt_input = self.query_one("#prompt_input", Input)
        prompt_input.clear()
        prompt_input.disabled = True

        chat_log = self.query_one("#chat_log", RichLog)
        chat_log.write(f"> {prompt}")

        self.run_worker(self.run_chat_task(prompt))

    def _blocking_chat_runner(self, prompt: str) -> None:
        """The synchronous, blocking method that runs the chat."""
        for chunk in self.coder.run_stream(prompt):
            self.post_message(self.UpdateChatLog(chunk))

        if self.coder.last_aider_commit_diff:
            self.post_message(
                self.ShowDiff(
                    self.coder.last_aider_commit_diff,
                    self.coder.last_aider_commit_message,
                )
            )

        self.post_message(self.ChatTaskDone())

    async def run_chat_task(self, prompt: str) -> None:
        """Run a chat task in a background thread."""
        await asyncio.to_thread(self._blocking_chat_runner, prompt)

    def _blocking_handle_file_selected(self, file_path: str):
        """Helper to add/remove file from chat in a thread."""
        rel_path = os.path.relpath(file_path, self.coder.root)

        in_chat_files = self.coder.get_inchat_relative_files()
        if rel_path in in_chat_files:
            self.coder.drop_rel_fname(rel_path)
            self.post_message(self.UpdateChatLog(f"Removed {rel_path} from the chat."))
        else:
            self.coder.add_rel_fname(rel_path)
            self.post_message(self.UpdateChatLog(f"Added {rel_path} from the chat."))

    async def handle_file_selected(self, file_path: str) -> None:
        """Handle file selection in a background thread."""
        await asyncio.to_thread(self._blocking_handle_file_selected, file_path)

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            Container(id="sidebar")
            with Container(id="chat-container"):
                yield RichLog(wrap=True, id="chat_log")
                yield Input(
                    placeholder="Loading Coder...",
                    id="prompt_input",
                    disabled=True,
                )
        yield Footer()

def run_tui(args):
    app = TuiApp(args)
    app.run()
