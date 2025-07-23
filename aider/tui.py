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
