import subprocess
import sys

import subprocess
import sys

from ..utils import format_messages
from .base_coder import Coder
from .base_prompts import CoderPrompts


class LLMCommandCoder(Coder):
    def __init__(self, main_model, io, **kwargs):
        self.llm_command = kwargs.get("llm_command")
        if not self.llm_command:
            raise ValueError("LLMCommandCoder requires llm_command")

        self.edit_format = kwargs.pop("edit_format", "diff-fenced")
        super().__init__(main_model, io, **kwargs)
        self.gpt_prompts = CoderPrompts()
        # some model settings are not applicable
        self.stream = True  # llm_command is always streaming
        self.main_model.streaming = True

    def get_edits(self, mode="update"):
        # TODO: implement parsing of diff-fenced blocks
        return []

    def send(self, messages, model=None, functions=None):
        if functions:
            self.io.tool_error("LLMCommandCoder does not support functions.")
            return

        self.partial_response_content = ""

        # The prompt is the plain text of the messages.
        prompt = "\n".join(m["content"] for m in messages if m.get("content"))
        self.io.log_llm_history("TO LLM", prompt)

        try:
            process = subprocess.Popen(
                self.llm_command,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            # Stream the prompt to the command
            if prompt:
                process.stdin.write(prompt)
            process.stdin.close()

            # Stream the output from the command
            completion = process.stdout

            for chunk in iter(lambda: completion.read(1), ""):
                if not chunk:
                    break

                self.partial_response_content += chunk
                if self.show_pretty():
                    self.live_incremental_response(False)
                else:
                    # sys.stdout.write(chunk)
                    # sys.stdout.flush()
                    pass
                yield chunk

            process.wait()
            if process.returncode != 0:
                stderr_output = process.stderr.read()
                self.io.tool_error(f"LLM command failed with exit code {process.returncode}")
                if stderr_output:
                    self.io.tool_error(stderr_output)

        except FileNotFoundError:
            self.io.tool_error(f"The command '{self.llm_command}' was not found.")
        except Exception as e:
            self.io.tool_error(f"Error running llm_command: {e}")

    def calculate_and_show_tokens_and_cost(self, messages, completion=None):
        # We can't know the tokens or cost for a shell command.
        self.usage_report = "Tokens: unknown, Cost: unknown for llm-command"
        return
