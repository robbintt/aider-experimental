from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
from textual.worker import worker

class TuiApp(App):
    """Aider's Textual TUI."""

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, args):
        self.args = args
        self.coder = None
        super().__init__()

    def on_mount(self) -> None:
        """Called when app starts."""
        # Use a worker to avoid blocking the UI during Coder setup
        self.run_coder_setup()

    @worker
    def run_coder_setup(self) -> None:
        """Setup the Coder in the background."""
        from aider.main import main as main_runner

        # Pass all args except the script name itself
        self.coder = main_runner(self.args, return_coder=True)
        # You might want to post a message to the UI thread
        # to enable the input once the coder is ready.

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(wrap=True, id="chat_log")
        yield Input(placeholder="Enter your prompt...", id="prompt_input")
        yield Footer()

def run_tui(args):
    app = TuiApp(args)
    app.run()
