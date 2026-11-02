#!/usr/bin/env python3
"""CPU test of ll_gate.py ablate (osdi/longlive/ablation_prereg.md) on the tiny random LongLive model of
test_ll_runtime.py: every condition builds the intended state at the cutover call (only its components restored or
perturbed, the snapshot itself never modified), the exact conditions reproduce the reference, W > M is skipped.

    python tools/longlive/test_ll_ablate.py
"""
import sys, types, json
sys.path.insert(0, "tools/longlive")
import torch
torch.set_grad_enabled(False)
import test_ll_runtime as T
import ll_gate as G
m = T.tiny_model()
a = types.SimpleNamespace(at=26, calls=40, seed=0, prompt="a boy on a lawn", eps=2.0 ** -8, conditions=G.ABLATE, out=None)
out = G.ablate(a, m)
c = out["conditions"]
fails = []
def chk(cond, msg):
    print(("  [ok] " if cond else "  [FAIL] ") + msg); cond or fails.append(msg)
chk(c["full"]["latents_equal_calls"] == 14 and c["full"]["psnr_windows"]["min"] == 99.0, "full import: exact on all scored calls")
chk(c["sink_win_vae"]["latents_equal_calls"] == 14, "sink + window + VAE (cross-attention recomputed, no latent buffer): exact")
chk(c["sink_win_vae"]["xattn_recomputed_exact"] is True, "cross-attention recomputed from the prompt equals R's")
chk(c["sink"]["state_at_M"]["window_layers_exact"] == 0 and not c["sink"]["state_at_M"]["vae_exact"], "sink only: window and VAE not restored")
chk(c["sink_win"]["state_at_M"]["window_layers_exact"] == 2 and not c["sink_win"]["state_at_M"]["vae_exact"], "sink + window: window exact, VAE cold")
chk(c["sink_vae"]["state_at_M"]["vae_exact"] and c["sink_vae"]["state_at_M"]["window_layers_exact"] == 0, "sink + VAE: VAE exact, window empty")
chk(c["w12_vaeX"]["state_at_M"]["vae_exact"] and c["w12"]["state_at_M"]["window_layers_exact"] == c["w12_vaeX"]["state_at_M"]["window_layers_exact"], "w12 + exact VAE: same window as w12, VAE exact")
for e in ("eps_win", "eps_vae", "eps_sink"):
    chk(c[e]["state_at_M"]["sink_exact"] == (e != "eps_sink"), f"{e}: only its component perturbed (sink exact {c[e]['state_at_M']['sink_exact']})")
chk("w48" not in c and "w96" not in c, "W > M skipped")
chk(all(c[n]["state_at_M"]["sink_exact"] for n in c if n != "eps_sink"), "sink exact in every other condition")
chk(c["eps_vae"]["state_at_M"]["vae_exact"] is False and c["eps_vae"]["state_at_M"]["vae_rel_err"] > 0, "eps_vae: VAE cache perturbed")
chk(c["eps_sink"]["state_at_M"]["vae_exact"] and c["eps_sink"]["state_at_M"]["window_layers_exact"] == 2, "eps_sink after eps_vae: snapshot not modified (VAE, window exact)")
chk(c["sink"]["state_at_M"]["vae_rel_err"] == 1.0 and c["sink"]["frames_missing"] == 3, "sink only: VAE cache missing (rel err 1), cold decoder drops 3 frames")
json.dumps(out)
print("ALL PASS" if not fails else f"FAILED {fails}")
sys.exit(1 if fails else 0)
