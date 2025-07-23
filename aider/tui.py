from textual.app import App, ComposeResult
from textual.message import Message
from textual.widgets import Header, Footer, Input, RichLog

class TuiApp(App):
    """Aider's Textual TUI."""

    class CoderReady(Message):
        """Posted when the Coder is ready."""

    BINDINGS = [("q", "quit", "Quit")]

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
        self.coder = await self.run_in_thread(main_runner, self.args, return_coder=True)
        self.post_message(self.CoderReady())

    def on_coder_ready(self, message: "TuiApp.CoderReady") -> None:
        """Enable the prompt input when the coder is ready."""
        prompt_input = self.query_one("#prompt_input", Input)
        prompt_input.disabled = False
        prompt_input.focus()
        prompt_input.placeholder = "Enter your prompt..."

    def compose(self) -> ComposeResult:
        yield Header()
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
