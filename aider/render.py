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
