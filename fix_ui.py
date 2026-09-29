# -*- coding: utf-8 -*-
import re

with open('src/ui/components/report_modal.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'\"is_cheat\": \(aim_snap > 18\.0 or aim_jerk > 30\.0 or \"AIMBOT\" in flags_str\),', '\"is_cheat\": (\"AIMBOT\" in flags_str),', text)
text = re.sub(r'\"is_suspect\": \(aim_snap > 10\.0 or aim_jerk > 18\.0\),', '\"is_suspect\": (\"AIMBOT\" in flags_str or \"Jerk\" in flags_str),', text)

text = re.sub(r'\"is_cheat\": \(wh_cache > 15\.0 or wh_track >= 10 or \"WALLHACK\" in flags_str or \"LOCK\" in flags_str\),', '\"is_cheat\": (\"WALLHACK\" in flags_str or \"INFO-ESP\" in flags_str or \"LOCK\" in flags_str),', text)
text = re.sub(r'\"is_suspect\": \(wh_cache > 5\.0 or wh_track >= 5\),', '\"is_suspect\": (\"Track\" in flags_str or \"INFO-ESP\" in flags_str),', text)

text = re.sub(r'\"is_cheat\": \(\(bhop_ratio > 70\.0 and bhop_chain >= 4\) or \"BHOP\" in flags_str\),', '\"is_cheat\": (\"BHOP\" in flags_str and \"Script\" in flags_str),', text)
text = re.sub(r'\"is_suspect\": \(bhop_ratio > 40\.0 and bhop_chain >= 3\),', '\"is_suspect\": (\"BHOP\" in flags_str or \"Chaîne\" in flags_str),', text)

text = re.sub(r'\"is_cheat\": \(spin_speed > 90\.0 or spin_pitch_viol > 0 or \"SPINBOT\" in flags_str or \"PITCH\" in flags_str\),', '\"is_cheat\": (\"SPINBOT\" in flags_str or \"PITCH\" in flags_str or \"ANTI-AIM\" in flags_str),', text)
text = re.sub(r'\"is_suspect\": \(spin_jitter > 2000\.0 or spin_desync >= 32 or \"ANTI-AIM\" in flags_str\),', '\"is_suspect\": (\"ANTI-AIM\" in flags_str or \"Jitter\" in flags_str),', text)

text = re.sub(r'\"is_cheat\": \(\(tb_shots >= 3 and tb_rt_med < 50\.0\) or \"TRIGGERBOT\" in flags_str\),', '\"is_cheat\": (\"TRIGGERBOT\" in flags_str or \"TRIGGER\" in flags_str),', text)
text = re.sub(r'\"is_suspect\": \(\(tb_shots >= 3 and tb_rt_std < 15\.0\) or tb_burst >= 1 or \"TRIGGER\" in flags_str\),', '\"is_suspect\": (\"TRIGGERBOT\" in flags_str or \"TRIGGER\" in flags_str),', text)

with open('src/ui/components/report_modal.py', 'w', encoding='utf-8') as f:
    f.write(text)
