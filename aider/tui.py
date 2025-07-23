import asyncio
import sys

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.widgets import Header, Footer, Input, RichLog

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

        def __init__(self, diff: str) -> None:
            super().__init__()
            self.diff = diff

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

        try:
            # main_runner is a synchronous function that does all the setup.
            # We run it in a thread to avoid blocking the UI.
            # It expects a list of command-line arguments (argv).
            self.coder = await asyncio.to_thread(main_runner, tui_args, return_coder=True)
            self.log("Coder setup finished.")
            self.post_message(self.CoderReady())
            self.log("Posted CoderReady message.")
        except Exception as e:
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

    def on_update_chat_log(self, message: "TuiApp.UpdateChatLog") -> None:
        """Update the chat log with a new message."""
        self.query_one("#chat_log", RichLog).write(message.text)

    def on_show_diff(self, message: "TuiApp.ShowDiff") -> None:
        """Show a diff in the chat log."""
        self.query_one("#chat_log", RichLog).write(f"```diff\n{message.diff}\n```")

    def on_chat_task_done(self, message: "TuiApp.ChatTaskDone") -> None:
        """Re-enable the prompt input when a chat task is done."""
        prompt_input = self.query_one("#prompt_input", Input)
        prompt_input.disabled = False
        prompt_input.focus()

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
            self.post_message(self.ShowDiff(self.coder.last_aider_commit_diff))

        self.post_message(self.ChatTaskDone())

    async def run_chat_task(self, prompt: str) -> None:
        """Run a chat task in a background thread."""
        await asyncio.to_thread(self._blocking_chat_runner, prompt)

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
