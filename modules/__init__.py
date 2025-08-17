from .aixutils.ai import setup_ai_handler
from .aixutils.dep import setup_dep_handler
from .aixutils.gemi import setup_gem_handler
from .aixutils.gpt import setup_gpt_handlers
from .aixutils.cla import setup_cla_handler
def setup_modules_handlers(app):
    setup_ai_handler(app)
    setup_dep_handler(app)
    setup_gem_handler(app)
    setup_gpt_handlers(app)
    setup_cla_handler(app)