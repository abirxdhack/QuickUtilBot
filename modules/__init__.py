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
from .decxutils.dutilz import setup_decoders_handler
from .fakexutils.fake import setup_fake_handler
from .gitxutils.git import setup_git_handler
from .hlpxutils.help import setup_help_handler
from .hlpxutils.tpusers import setup_tp_handler
from .privxutils.privacy import setup_privacy_handler
from .infoxutils.info import setup_info_handler
from .mailxutils.tmail import setup_tmail_handler
from .mailxutils.fmail import setup_fmail_handlers
from .timexutils.time import setup_time_handler
from .grpxutils.wlc import setup_wlc_handler
from .txtutils.sptxt import setup_txt_handler

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
    setup_decoders_handler(app)
    setup_fake_handler(app)
    setup_git_handler(app)
    setup_help_handler(app)
    setup_tp_handler(app)
    setup_privacy_handler(app)
    setup_info_handler(app)
    setup_fmail_handlers(app)
    setup_tmail_handler(app)
    setup_time_handler(app)
    setup_wlc_handler(app)
    setup_txt_handler(app)
