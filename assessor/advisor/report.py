"""Gera `data/RELATORIO.md` legível a partir do relatório JSON e do banco.
Chamado ao fim de cada execução do monitor."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .storage import MonitorDB


def build(db_path: str = "data/monitor.db", report_json: str = "data/relatorio.json",
          out: str = "data/RELATORIO.md") -> str:
    db = MonitorDB(db_path)
    rep = json.loads(Path(report_json).read_text(encoding="utf-8")) if Path(report_json).exists() else {}
    s = db.summary()
    lines = [f"# Monitor de influenciadores", "",
             f"Atualizado em {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", "",
             "| Posts | Autores | Campanhas | Sinais | Preços |", "|---|---|---|---|---|",
             f"| {s['posts']} | {s['autores']} | {s['campanhas']} | {s['sinais']} | {s['precos']} |", ""]
    camps = rep.get("campanhas", [])
    lines += ["## Campanhas nos últimos 30 dias", ""]
    if not camps:
        lines.append("Nenhuma campanha coordenada detectada (3+ autores, mesmo ativo e direção em 24h).")
    else:
        lines += ["| Ativo | Direção | Autores | Líder | Fase | Ação | Confiança |", "|---|---|---|---|---|---|---|"]
        for c in camps:
            lines.append(f"| {c['ativo']} | {c['direcao']} | {c['autores']} | {c['lider']} | {c['fase']} | {c['acao']} | {c['confianca']:.2f} |")
    groups = rep.get("grupos_descobertos", [])
    lines += ["", "## Grupos descobertos (postam juntos em 2+ campanhas)", ""]
    lines += [f"- {', '.join(g)}" for g in groups] or ["Nenhum ainda: precisa de campanhas repetidas."]
    leaders = rep.get("lideres", [])
    lines += ["", "## Quem posta primeiro", ""]
    lines += [f"- {a}: {n:+d}" for a, n in leaders[:10]] or ["Sem dados."]
    cur = db.conn.execute("SELECT author_key, COUNT(*) n FROM posts GROUP BY author_key ORDER BY n DESC LIMIT 15")
    lines += ["", "## Autores mais ativos (total coletado)", ""]
    lines += [f"- {a}: {n} posts" for a, n in cur.fetchall()] or ["Sem dados."]
    cur = db.conn.execute("SELECT t.value AS ticker, COUNT(*) n FROM posts, json_each(posts.tickers) t GROUP BY t.value ORDER BY n DESC LIMIT 15")
    lines += ["", "## Ativos mais mencionados", ""]
    lines += [f"- {t}: {n}" for t, n in cur.fetchall()] or ["Sem dados."]
    cur = db.conn.execute("SELECT finished_at, n_posts, errors FROM runs ORDER BY finished_at DESC LIMIT 1")
    row = cur.fetchone()
    if row:
        errs = json.loads(row[2] or "[]")
        lines += ["", f"## Última execução: {row[0]} ({row[1]} posts novos, {len(errs)} erros)", ""]
        lines += [f"- {e}" for e in errs[:20]]
    text = "\n".join(lines) + "\n"
    Path(out).write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(build())
