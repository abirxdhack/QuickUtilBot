#Copyright @ISmartCoder
#Updates Channel t.me/TheSmartDev

from .aixutils.ai import setup_ai_handler
from .aixutils.dep import setup_dep_handler
from .aixutils.gemi import setup_gem_handler
from .aixutils.gpt import setup_gpt_handlers
from .aixutils.cla import setup_cla_handler
from .ccxutils.binf import setup_binf_handlers
from .ccxutils.db import setup_db_handlers
from .ccxutils.extp import setup_extp_handler
from .ccxutils.fcc import setup_fcc_handler
from .ccxutils.mbin import setup_mbin_handler
from .ccxutils.mgen import setup_multi_handler
from .ccxutils.top import setup_topbin_handler
from .ccxutils.gen import setup_gen_handler
from .ccxutils.bin import setup_bin_handler
from .cryptxutils.cryptdata import setup_binance_handler
from .cryptxutils.cryptx import setup_coin_handler
from .cryptxutils.p2p import setup_p2p_handler
from .cryptxutils.token import setup_crypto_handler

def setup_modules_handlers(app):
    setup_ai_handler(app)
    setup_dep_handler(app)
    setup_gem_handler(app)
    setup_gpt_handlers(app)
    setup_cla_handler(app)
    setup_binf_handlers(app)
    setup_db_handlers(app)
    setup_extp_handler(app)
    setup_fcc_handler(app)
    setup_mbin_handler(app)
    setup_multi_handler(app)
    setup_topbin_handler(app)
    setup_gen_handler(app)
    setup_bin_handler(app)
    setup_binance_handler(app)
    setup_coin_handler(app)
    setup_p2p_handler(app)
    setup_crypto_handler(app)
