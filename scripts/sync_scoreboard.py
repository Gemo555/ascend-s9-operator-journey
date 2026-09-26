"""Archive a supplied scoreboard and render its explicitly provisional results."""
import argparse
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import posixpath

ROOT = Path(__file__).resolve().parents[1]
TEAM = "本质嘉豪"
SLUGS = {"Concat": "concat", "Greater": "greater", "IndexAdd": "indexadd",
         "Transpose": "transpose", "SquareSumV1": "squaresumv1"}
START, END = "<!-- scoreboard:start -->", "<!-- scoreboard:end -->"


def summarize(raw, source_path):
    data = json.loads(raw.decode("utf-8-sig"), parse_float=Decimal)
    stamp = datetime.fromisoformat(data["updatedAt"])
    if stamp.utcoffset() is None:
        raise ValueError("Snapshot timestamp must include a timezone")
    if len(data["topics"]) != 5 or {t["name"] for t in data["topics"]} != set(SLUGS):
        raise ValueError("Expected exactly the five S9 topics")
    scores, ranks, own = {}, {}, []
    by_topic = {t["name"]: t for t in data["topics"]}
    for name in SLUGS:
        topic = by_topic[name]
        seen, topic_ranks = set(), set()
        team_row = None
        for row in topic["leaders"]:
            rank, points, team = row["rank"], row["points"], row["team"]
            if team in seen or rank in topic_ranks or not 1 <= rank <= 10:
                raise ValueError(f"Invalid or duplicate entry in {name}")
            if points != 110 - rank * 10 or Decimal(str(row["takeTime"])) < 0:
                raise ValueError(f"Invalid points/time in {name}")
            seen.add(team)
            topic_ranks.add(rank)
            scores.setdefault(team, {})[name] = points
            ranks.setdefault(team, {})[name] = rank
            if team == TEAM:
                team_row = row
        if topic_ranks != set(range(1, 11)):
            raise ValueError(f"Incomplete captured top ten for {name}")
        own.append({"name": name, "rank": team_row["rank"] if team_row else None,
                    "points": team_row["points"] if team_row else 0,
                    "time_us": str(team_row["takeTime"]) if team_row else None,
                    "last_commit": team_row["lastCommit"] if team_row else None,
                    "total_entries": topic["totalEntries"],
                    "final_package_id": None})
    totals = {team: sum(values.values()) for team, values in scores.items()}
    computed = {team: 1 + sum(other > total for other in totals.values())
                for team, total in totals.items()}
    standing_rows = data["standings"]
    if len(standing_rows) != len(totals) or {r["team"] for r in standing_rows} != set(totals):
        raise ValueError("Standings do not match captured topic leaders")
    for row in standing_rows:
        team = row["team"]
        if row["total"] != totals[team] or row["rank"] != computed[team]:
            raise ValueError(f"Inconsistent aggregate standing: {team}")
        for name in SLUGS:
            if row["scores"].get(name, 0) != scores[team].get(name, 0):
                raise ValueError(f"Inconsistent topic score: {team}/{name}")
            if name in ranks[team] and row["ranks"].get(name) != ranks[team][name]:
                raise ValueError(f"Inconsistent topic rank: {team}/{name}")
    if sum(totals.values()) != data["totalAwardedPoints"]:
        raise ValueError("Total awarded points mismatch")
    total = totals.get(TEAM, 0)
    return {"schema_version": 1, "status": "leaderboard_snapshot_not_final",
            "contest": data["contest"], "team": TEAM,
            "snapshot_time": data["updatedAt"], "source_url": data["source"],
            "source_file": source_path, "source_sha256": hashlib.sha256(raw).hexdigest(),
            "total_points": total, "aggregate_rank": computed.get(TEAM),
            "tied": total > 0 and sum(t == total for t in totals.values()) > 1,
            "scored_teams": len(totals), "registered_teams": data["registeredTeams"],
            "all_topics_top10": all(t["rank"] is not None for t in own),
            "topics": own, "final_result": None}


def relative(target, doc):
    return posixpath.relpath(target, posixpath.dirname(doc) or ".")


def render(summary, doc, topic=None):
    source = relative(summary["source_file"], doc)
    stamp = datetime.fromisoformat(summary["snapshot_time"]).isoformat(sep=" ")
    if topic:
        if topic["rank"] is None:
            headline = "此快照未收录本队该题前十记录；耗时与实际名次未知，积分为 0。"
        else:
            headline = (f"**榜单快照：第 {topic['rank']} 名 · {topic['points']} 分 · "
                        f"{topic['time_us']} μs。**")
        return (f"{headline}\n\n时间：{stamp}。"
                f"[原始快照]({source})；最终验收结果与对应提交包待确认。")
    if doc == "README.md":
        han_rank = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
                    6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}
        rank = summary["aggregate_rank"]
        rank_label = han_rank.get(rank, str(rank))
        lines = [f"<strong>总积分位列{summary['registered_teams']}支报名队的第{rank_label}名·</strong>"
                 f"{'五题均位列前十' if summary['all_topics_top10'] else '详见各题成绩'}", "",
                 "| 赛题 | 耗时（μs） | 单题名次 |", "|---|---:|---:|"]
        for t in summary["topics"]:
            path = f"topics/README.md#{SLUGS[t['name']]}"
            lines.append(f"| [{t['name']}]({path}) | {t['time_us'] or '未知'} | "
                         f"{t['rank'] or '未收录'} |")
        return "\n".join(lines)
    rank = summary["aggregate_rank"]
    rank_text = ("并列" if summary["tied"] else "") + f"第 {rank} 名" if rank else "未获积分"
    top_text = " · 五题全部进入前十" if summary["all_topics_top10"] else ""
    lines = [f"**积分汇总{rank_text} · {summary['total_points']} 分{top_text}**", "",
             f"> 截至 **{stamp}** 的榜单快照。最终比赛结果待团队确认。", "",
             "| 赛题 | 单题名次 | 积分 | 耗时 / μs | 上榜条目 |",
             "|---|---:|---:|---:|---:|"]
    for t in summary["topics"]:
        path = relative(f"operators/{SLUGS[t['name']]}/README.md", doc)
        lines.append(f"| [{t['name']}]({path}) | {t['rank'] or '未收录'} | {t['points']} | "
                     f"{t['time_us'] or '未知'} | {t['total_entries']} |")
    lines.extend(["", f"来源：[历史快照]({source})；积分榜由五题积分汇总，同分并列。"
                  f"快照记载 {summary['registered_teams']} 支报名队伍、"
                  f"{summary['scored_teams']} 支获得积分的队伍。"])
    return "\n".join(lines)


def rendered_documents(summary):
    docs = {"README.md": None, "docs/results.md": None}
    docs.update({f"operators/{SLUGS[t['name']]}/README.md": t for t in summary["topics"]})
    updated = {}
    for doc, topic in docs.items():
        content = (ROOT / doc).read_text(encoding="utf-8")
        if content.count(START) != 1 or content.count(END) != 1:
            raise ValueError(f"Missing or duplicated scoreboard markers: {doc}")
        before, after = content.split(START)
        _, rest = after.split(END)
        updated[doc] = before + START + "\n" + render(summary, doc, topic) + "\n" + END + rest
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    raw = args.source.read_bytes()
    stamp = datetime.fromisoformat(json.loads(raw.decode("utf-8-sig"))["updatedAt"])
    source = f"data/leaderboards/{stamp.strftime('%Y%m%d-%H%M%S%z')}.json"
    summary = summarize(raw, source)
    existing = ROOT / "data/results.json"
    if existing.exists():
        old = json.loads(existing.read_text(encoding="utf-8"))
        if old.get("final_result") is not None:
            raise ValueError("Final result present: explicitly reconcile it before importing a snapshot")
        if stamp < datetime.fromisoformat(old["snapshot_time"]):
            raise ValueError("Refusing to replace the current display with an older snapshot")
    outputs = rendered_documents(summary)
    target = ROOT / source
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("A different snapshot already exists at this timestamp")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    outputs["data/results.json"] = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    for name, content in outputs.items():
        (ROOT / name).write_text(content, encoding="utf-8", newline="\n")
    print(f"Imported {source}; points={summary['total_points']}, rank={summary['aggregate_rank']}")


if __name__ == "__main__":
    main()
