"""CLI mínima: python -m advisor.cli <comando> ...

Comandos:
  size       --capital 100000 --entry 30 --stop 28.5 [--risk 0.01]
  option     --spot 30 --strike 32 --days 30 --rate 0.11 --vol 0.35 [--type call] [--q 0]
  iv         --price 1.2 --spot 30 --strike 32 --days 30 --rate 0.11 [--type call]
  strategy   --name bull_call --args 30,1.5,33,0.5  (ver strategies.py p/ ordem dos args)
  sources    [--kind oficial|alternativa] [--market BR|US|cripto]
  week       --start 100000 --end 103500 [--withdraw 0.7]
  herd       --posts posts.jsonl [--window 24] [--min-authors 3] [--stats stats.json]
             (posts.jsonl: uma linha por post com author, platform, ts, text, engagement)
"""
from __future__ import annotations

import argparse
import json
from datetime import date

from . import options, risk
from .data.sources import list_sources
from .portfolio.weekly import WeeklyCycle


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="advisor")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("size"); s.add_argument("--capital", type=float, required=True)
    s.add_argument("--entry", type=float, required=True); s.add_argument("--stop", type=float, required=True)
    s.add_argument("--risk", type=float, default=0.01); s.add_argument("--lot", type=int, default=1)

    o = sub.add_parser("option")
    for a in ("spot", "strike", "days", "rate", "vol"):
        o.add_argument(f"--{a}", type=float, required=True)
    o.add_argument("--type", default="call"); o.add_argument("--q", type=float, default=0.0)

    iv = sub.add_parser("iv")
    for a in ("price", "spot", "strike", "days", "rate"):
        iv.add_argument(f"--{a}", type=float, required=True)
    iv.add_argument("--type", default="call")

    st = sub.add_parser("strategy"); st.add_argument("--name", required=True); st.add_argument("--args", required=True)

    src = sub.add_parser("sources"); src.add_argument("--kind"); src.add_argument("--market")

    w = sub.add_parser("week"); w.add_argument("--start", type=float, required=True)
    w.add_argument("--end", type=float, required=True); w.add_argument("--withdraw", type=float, default=0.7)
    w.add_argument("--capital", type=float)

    h = sub.add_parser("herd"); h.add_argument("--posts", required=True)
    h.add_argument("--window", type=float, default=24.0); h.add_argument("--min-authors", type=int, default=3)
    h.add_argument("--stats")

    a = p.parse_args(argv)
    if a.cmd == "size":
        b = risk.RiskBudget(a.capital, max_risk_per_trade=a.risk)
        print(json.dumps(risk.position_size(b, a.entry, a.stop, lot=a.lot).__dict__, indent=2, ensure_ascii=False))
    elif a.cmd == "option":
        t = a.days / 365
        price = options.black_scholes(a.spot, a.strike, t, a.rate, a.vol, a.type, a.q)
        g = options.greeks(a.spot, a.strike, t, a.rate, a.vol, a.type, a.q)
        amer = options.binomial_american(a.spot, a.strike, t, a.rate, a.vol, a.type, a.q)
        print(json.dumps({"bsm_europeia": price, "binomial_americana": amer, **g.__dict__}, indent=2))
    elif a.cmd == "iv":
        print(options.implied_volatility(a.price, a.spot, a.strike, a.days / 365, a.rate, a.type))
    elif a.cmd == "strategy":
        fn = getattr(options, a.name if a.name.endswith("spread") or hasattr(options, a.name) else a.name)
        nums = [float(x) for x in a.args.split(",")]
        print(json.dumps(fn(*nums).summary(), indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "sources":
        for src_ in list_sources(a.kind, a.market):
            print(f"[{src_.kind:11}] {src_.market:6} {src_.name}: {src_.what} ({src_.latency})")
    elif a.cmd == "week":
        b = risk.RiskBudget(a.capital or a.start)
        rep = WeeklyCycle(b, a.withdraw).close_week(date.today(), a.start, a.end)
        print(json.dumps(rep.__dict__, indent=2, ensure_ascii=False, default=str))
    elif a.cmd == "herd":
        from .influencers import parse_posts_jsonl, detect_campaigns, CoMentionGraph, clusters, herd_signal
        posts = parse_posts_jsonl(a.posts)
        stats = json.loads(open(a.stats, encoding="utf-8").read()) if a.stats else {}
        camps = detect_campaigns(posts, a.window, a.min_authors)
        g = CoMentionGraph.from_campaigns(camps)
        out = {
            "campanhas": [{**c.summary(), "sinal": herd_signal(c, stats).__dict__} for c in camps],
            "grupos_descobertos": clusters(g),
            "lideres": g.leaders()[:10],
        }
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
