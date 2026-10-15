"""`empirica session-close` — end sessions as closed-unassessed.

For sessions that cannot honestly be POSTFLIGHTed (no grounded state to
assess). Writes end_time, status='closed-unassessed' and the reason into
session_notes. Writes no epistemic vectors. Previews unless --apply.
"""

import json


def handle_session_close_command(args):
    """Close one or more sessions as closed-unassessed."""
    from empirica.data.session_database import SessionDatabase

    session_ids = list(dict.fromkeys(args.session_ids))  # de-duplicate, keep order
    db = SessionDatabase()
    results = []
    try:
        for sid in session_ids:
            row = db.sessions.get_session(sid)
            if row is None:
                results.append({"session_id": sid, "action": "not_found"})
                continue
            if row.get("end_time"):
                results.append({"session_id": sid, "action": "already_ended", "status": row.get("status")})
                continue
            if not args.apply:
                results.append({"session_id": sid, "action": "would_close"})
                continue
            closed = db.sessions.close_session_unassessed(sid, args.reason)
            results.append({"session_id": sid, "action": "closed-unassessed" if closed else "skipped"})
    finally:
        db.close()

    payload = {
        "ok": True,
        "applied": bool(args.apply),
        "reason": args.reason,
        "requested": len(session_ids),
        "closed": sum(1 for r in results if r["action"] == "closed-unassessed"),
        "results": results,
    }
    if args.output == "json":
        print(json.dumps(payload, indent=2))
    else:
        mode = "Closed" if args.apply else "Would close (preview — pass --apply to write)"
        print(f"{mode}: {payload['closed'] if args.apply else sum(1 for r in results if r['action'] == 'would_close')} of {len(session_ids)}")
        for r in results:
            print(f"  {r['session_id']}  {r['action']}")
    return 0
