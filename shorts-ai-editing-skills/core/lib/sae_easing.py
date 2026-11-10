"""Easing functions shared by all skills, plus FFmpeg-expression equivalents.

Adds `back-out` (overshoot then settle) for "pop" moves — missing from V1.1's four easings.
All functions map u in [0,1] -> value, with f(0)=0 and f(1)=1.
"""
from __future__ import annotations

BACK_S = 1.70158 * 0.6  # gentle overshoot (~6% at peak) — readable, not cartoony

EASE = {
    "linear": lambda u: u,
    "ease-in": lambda u: u * u,
    "ease-out": lambda u: 1 - (1 - u) * (1 - u),
    "ease-in-out": lambda u: 2 * u * u if u < 0.5 else 1 - 2 * (1 - u) * (1 - u),
    "back-out": lambda u: 1 + (BACK_S + 1) * (u - 1) ** 3 + BACK_S * (u - 1) ** 2,
    "step": lambda u: 1.0,
}

EXPR = {
    "linear": "({u})",
    "ease-in": "(({u})*({u}))",
    "ease-out": "(1-(1-({u}))*(1-({u})))",
    "ease-in-out": "if(lt({u},0.5),2*({u})*({u}),1-2*(1-({u}))*(1-({u})))",
    "back-out": "(1+" + f"{BACK_S + 1:.6f}" + "*pow(({u})-1,3)+" + f"{BACK_S:.6f}" + "*pow(({u})-1,2))",
    "step": "1",
}


def peak(name: str, steps: int = 200) -> float:
    return max(EASE[name](i / steps) for i in range(steps + 1))
