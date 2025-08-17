#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev
from .admin.admin import setup_admin_handler
from .logs.logs import setup_logs_handler
from .restart.restart import setup_restart_handler
from .sudo.sudo import setup_sudo_handler
from .speedtest.speedtest import setup_speed_handler
from .settings.settings import setup_settings_handler
from .gban.gban import setup_gban_handler

def setup_sudoers_handlers(app):
    setup_admin_handler(app)
    setup_logs_handler(app)
    setup_restart_handler(app)
    setup_sudo_handler(app)
    setup_speed_handler(app)
    setup_settings_handler(app)
    setup_gban_handler(app)

