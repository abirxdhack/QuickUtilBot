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
from .ytxutils.yth import setup_yth_handler
from .ytxutils.ytag import setup_ytag_handlers
from .toolxutils.cpn import setup_cpn_handler
from .toolxutils.enh import setup_enh_handler
from .toolxutils.fdl import setup_fdl_handler
from .toolxutils.getusr import setup_getusr_handler
from .toolxutils.rs import setup_rs_handler
from .toolxutils.vnote import setup_vnote_handler
from .sessxutils.string import setup_string_handler
from .webxutils.ws import setup_ws_handler
from .webxutils.ss import setup_ss_handler
from .audxutils.aud import setup_voice_handler
from .audxutils.conv import setup_aud_handler
from .stickxutils.quote import setup_q_handler
from .stickxutils.kang import setup_kang_handler
from .netxutils.dmn import setup_dmn_handlers
from .netxutils.ip import setup_ip_handlers
from .netxutils.ocr import setup_ocr_handler
from .netxutils.px import setup_px_handler
from .netxutils.sk import setup_sk_handlers
from .eduxutils.gmr import setup_gmr_handler
from .eduxutils.pron import setup_prn_handler
from .eduxutils.spl import setup_spl_handler
from .eduxutils.syn import setup_syn_handler
from .eduxutils.tr import setup_tr_handler
from .payxutils.pay import setup_donate_handler
from .dlxutils.tik import setup_tt_handler
from .dlxutils.yt import setup_yt_handler
from .dlxutils.fb import setup_fb_handlers
from .dlxutils.pnt import setup_pinterest_handler
from .dlxutils.insta import setup_insta_handlers
from .dlxutils.spfy import setup_spotify_handler
from .dlxutils.tx import setup_tx_handler

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
    setup_yth_handler(app)
    setup_ytag_handlers(app)
    setup_cpn_handler(app)
    setup_enh_handler(app)
    setup_fdl_handler(app)
    setup_getusr_handler(app)
    setup_rs_handler(app)
    setup_vnote_handler(app)
    setup_string_handler(app)
    setup_ws_handler(app)
    setup_ss_handler(app)
    setup_aud_handler(app)
    setup_voice_handler(app)
    setup_q_handler(app)
    setup_kang_handler(app)
    setup_dmn_handlers(app)
    setup_ip_handlers(app)
    setup_ocr_handler(app)
    setup_px_handler(app)
    setup_sk_handlers(app)
    setup_gmr_handler(app)
    setup_prn_handler(app)
    setup_spl_handler(app)
    setup_syn_handler(app)
    setup_tr_handler(app)
    setup_donate_handler(app)
    setup_tt_handler(app)
    setup_yt_handler(app)
    setup_fb_handlers(app)
    setup_pinterest_handler(app)
    setup_insta_handlers(app)
    setup_spotify_handler(app)
    setup_tx_handler(app)
