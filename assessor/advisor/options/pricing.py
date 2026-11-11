"""Precificação de opções: Black-Scholes-Merton, gregas, vol implícita e
binomial para americanas. Implementação em Python puro (sem scipy).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"


SQRT_2PI = math.sqrt(2 * math.pi)


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT_2PI


def _d1_d2(s: float, k: float, t: float, r: float, sigma: float, q: float):
    if t <= 0 or sigma <= 0:
        raise ValueError("t e sigma devem ser positivos")
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    return d1, d2


def black_scholes(s: float, k: float, t: float, r: float, sigma: float,
                  option_type: OptionType | str = OptionType.CALL, q: float = 0.0) -> float:
    """Preço BSM. s=spot, k=strike, t=anos até vencimento, r=taxa livre de
    risco contínua, sigma=vol anual, q=dividend yield contínuo."""
    option_type = OptionType(option_type)
    if t <= 0:
        return max(0.0, s - k) if option_type is OptionType.CALL else max(0.0, k - s)
    d1, d2 = _d1_d2(s, k, t, r, sigma, q)
    if option_type is OptionType.CALL:
        return s * math.exp(-q * t) * norm_cdf(d1) - k * math.exp(-r * t) * norm_cdf(d2)
    return k * math.exp(-r * t) * norm_cdf(-d2) - s * math.exp(-q * t) * norm_cdf(-d1)


@dataclass(frozen=True)
class Greeks:
    delta: float
    gamma: float
    vega: float    # por 1 ponto percentual de vol
    theta: float   # por dia corrido
    rho: float     # por 1 ponto percentual de juros


def greeks(s: float, k: float, t: float, r: float, sigma: float,
           option_type: OptionType | str = OptionType.CALL, q: float = 0.0) -> Greeks:
    option_type = OptionType(option_type)
    d1, d2 = _d1_d2(s, k, t, r, sigma, q)
    sq_t = math.sqrt(t)
    eq = math.exp(-q * t)
    er = math.exp(-r * t)
    pdf = norm_pdf(d1)
    gamma = eq * pdf / (s * sigma * sq_t)
    vega = s * eq * pdf * sq_t / 100
    if option_type is OptionType.CALL:
        delta = eq * norm_cdf(d1)
        theta = (-s * eq * pdf * sigma / (2 * sq_t) - r * k * er * norm_cdf(d2)
                 + q * s * eq * norm_cdf(d1)) / 365
        rho = k * t * er * norm_cdf(d2) / 100
    else:
        delta = -eq * norm_cdf(-d1)
        theta = (-s * eq * pdf * sigma / (2 * sq_t) + r * k * er * norm_cdf(-d2)
                 - q * s * eq * norm_cdf(-d1)) / 365
        rho = -k * t * er * norm_cdf(-d2) / 100
    return Greeks(delta, gamma, vega, theta, rho)


def implied_volatility(price: float, s: float, k: float, t: float, r: float,
                       option_type: OptionType | str = OptionType.CALL, q: float = 0.0,
                       tol: float = 1e-8, max_iter: int = 200) -> float:
    """Vol implícita por bisseção (robusta) refinada por Newton."""
    option_type = OptionType(option_type)
    intrinsic = black_scholes(s, k, t, r, 1e-9 if t > 0 else 0, option_type, q) if t > 0 else 0
    if price < intrinsic - 1e-12:
        raise ValueError("preço abaixo do valor intrínseco descontado: sem IV")
    lo, hi = 1e-6, 5.0
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        diff = black_scholes(s, k, t, r, mid, option_type, q) - price
        if abs(diff) < tol:
            return mid
        if diff > 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def binomial_american(s: float, k: float, t: float, r: float, sigma: float,
                      option_type: OptionType | str = OptionType.CALL, q: float = 0.0,
                      steps: int = 200) -> float:
    """Árvore binomial CRR com exercício antecipado (opções americanas, padrão
    na B3 para opções de ações)."""
    option_type = OptionType(option_type)
    dt = t / steps
    u = math.exp(sigma * math.sqrt(dt))
    d = 1 / u
    p = (math.exp((r - q) * dt) - d) / (u - d)
    disc = math.exp(-r * dt)
    sign = 1 if option_type is OptionType.CALL else -1
    values = [max(0.0, sign * (s * u**j * d**(steps - j) - k)) for j in range(steps + 1)]
    for i in range(steps - 1, -1, -1):
        for j in range(i + 1):
            cont = disc * (p * values[j + 1] + (1 - p) * values[j])
            spot = s * u**j * d**(i - j)
            values[j] = max(cont, sign * (spot - k))
    return values[0]
