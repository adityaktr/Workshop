import db

CAPACITY = 800

class RequestError(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message


def list_appliances():
    conn = db.connect()
    try:
        rows = conn.execute(
            """
            SELECT id, name, wattage, priority, status
            FROM appliances
            ORDER BY priority ASC, name COLLATE NOCASE ASC, id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def create_appliance(name, wattage, priority):
    cleaned = name.strip()
    if not cleaned:
        raise RequestError(400, "Name is required.")
    if not isinstance(wattage, int) or wattage <= 0:
        raise RequestError(400, "Wattage must be a positive whole number.")
    if not isinstance(priority, int) or priority < 1:
        raise RequestError(400, "Priority must be 1 or higher.")

    conn = db.connect()
    try:
        cursor = conn.execute(
            """
            INSERT INTO appliances (name, wattage, priority)
            VALUES (?, ?, ?)
            """,
            (cleaned, wattage, priority),
        )
        row = conn.execute(
            "SELECT id, name, wattage, priority, status FROM appliances WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def delete_appliance(appliance_id):
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT id, name, wattage, priority, status FROM appliances WHERE id = ?",
            (appliance_id,),
        ).fetchone()
        if row is None:
            raise RequestError(404, f"No appliance with id {appliance_id}.")
        conn.execute("DELETE FROM appliances WHERE id = ?", (appliance_id,))
        return dict(row)
    finally:
        conn.close()


def list_running_appliances():
    conn = db.connect()
    try:
        rows = conn.execute(
            """
            SELECT id, name, wattage, priority, status
            FROM appliances
            WHERE status = 'running'
            ORDER BY priority ASC, wattage DESC, id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_shed_appliances():
    conn = db.connect()
    try:
        rows = conn.execute(
            """
            SELECT id, name, wattage, priority, status
            FROM appliances
            WHERE status = 'shed'
            ORDER BY priority ASC, wattage DESC, id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def total_running_wattage():
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(wattage), 0) AS total FROM appliances WHERE status = 'running'"
        ).fetchone()
        return row["total"]
    finally:
        conn.close()


def turn_on(appliance_id):
    def operation(conn):
        target = get_appliance(conn, appliance_id)
        if target["status"] == "running":
            total = running_total(conn)
            return {
                "message": f"{target['name']} is already running. Load is {total}W.",
                "shed": [],
                "restored": [],
                "total_wattage": total,
            }

        running = running_rows(conn)
        load = sum(item["wattage"] for item in running)
        deficit = load + target["wattage"] - CAPACITY
        eligible = [item for item in running if item["priority"] > target["priority"]]
        shed = choose_shed_set(eligible, deficit)
        if shed is None:
            raise RequestError(409, reject_message(target, running))

        for item in shed:
            conn.execute(
                "UPDATE appliances SET status = 'shed' WHERE id = ?",
                (item["id"],),
            )
        conn.execute(
            "UPDATE appliances SET status = 'running' WHERE id = ?",
            (appliance_id,),
        )
        restored = restore_what_fits(conn)
        total = running_total(conn)
        return {
            "message": result_message(f"Turned {target['name']} on.", shed, restored, total),
            "shed": shed,
            "restored": restored,
            "total_wattage": total,
        }

    return change(operation)


def turn_off(appliance_id):
    def operation(conn):
        target = get_appliance(conn, appliance_id)
        if target["status"] == "off":
            total = running_total(conn)
            return {
                "message": f"{target['name']} is already off.",
                "shed": [],
                "restored": [],
                "total_wattage": total,
            }

        was_running = target["status"] == "running"
        conn.execute(
            "UPDATE appliances SET status = 'off' WHERE id = ?",
            (appliance_id,),
        )
        restored = restore_what_fits(conn) if was_running else []
        total = running_total(conn)
        if was_running:
            lead = f"Turned {target['name']} off. That freed {target['wattage']}W."
        else:
            lead = (
                f"Turned {target['name']} off. It was shed and waiting; "
                "it will stay off until you turn it on."
            )
        return {
            "message": result_message(lead, [], restored, total),
            "shed": [],
            "restored": restored,
            "total_wattage": total,
        }

    return change(operation)


def change(operation):
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        result = operation(conn)
        if running_total(conn) > CAPACITY:
            raise RuntimeError(f"Load went over {CAPACITY}W.")
        conn.execute("COMMIT")
        return result
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def get_appliance(conn, appliance_id):
    row = conn.execute(
        "SELECT id, name, wattage, priority, status FROM appliances WHERE id = ?",
        (appliance_id,),
    ).fetchone()
    if row is None:
        raise RequestError(404, f"No appliance with id {appliance_id}.")
    return dict(row)


def running_rows(conn):
    rows = conn.execute(
        """
        SELECT id, name, wattage, priority, status
        FROM appliances
        WHERE status = 'running'
        ORDER BY priority ASC, wattage DESC, id ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def shed_rows(conn):
    rows = conn.execute(
        """
        SELECT id, name, wattage, priority, status
        FROM appliances
        WHERE status = 'shed'
        ORDER BY priority ASC, wattage DESC, id ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def running_total(conn):
    row = conn.execute(
        "SELECT COALESCE(SUM(wattage), 0) AS total FROM appliances WHERE status = 'running'"
    ).fetchone()
    return row["total"]


def choose_shed_set(eligible, deficit):
    if deficit <= 0:
        return []

    best = None
    best_key = None
    count = len(eligible)
    for mask in range(1, 1 << count):
        subset = [eligible[index] for index in range(count) if mask & (1 << index)]
        watts = sum(item["wattage"] for item in subset)
        if watts < deficit:
            continue
        key = (
            len(subset),
            tuple(sorted(-item["priority"] for item in subset)),
            watts,
            tuple(sorted(item["id"] for item in subset)),
        )
        if best_key is None or key < best_key:
            best_key = key
            best = subset
    return best


def restore_what_fits(conn):
    restored = []
    while True:
        remaining = CAPACITY - running_total(conn)
        pick = next((item for item in shed_rows(conn) if item["wattage"] <= remaining), None)
        if pick is None:
            break
        conn.execute(
            "UPDATE appliances SET status = 'running' WHERE id = ?",
            (pick["id"],),
        )
        restored.append(pick)
    return restored


def describe(items):
    return ", ".join(
        f"{item['name']} ({item['wattage']}W, priority {item['priority']})"
        for item in items
    )


def reject_message(target, running):
    load = sum(item["wattage"] for item in running)
    need = load + target["wattage"] - CAPACITY
    eligible = [item for item in running if item["priority"] > target["priority"]]
    protected = [item for item in running if item["priority"] <= target["priority"]]
    protected_text = describe(protected) or "none"

    if target["wattage"] > CAPACITY:
        return (
            f"Cannot turn on {target['name']}: it is {target['wattage']}W "
            f"and the inverter limit is {CAPACITY}W. Nothing was changed."
        )
    if not eligible:
        return (
            f"Cannot turn on {target['name']} ({target['wattage']}W, priority {target['priority']}). "
            f"Load is {load}W, so it needs {need}W freed. "
            f"No running appliance has a worse priority, so nothing can be shed. "
            f"Left untouched: {protected_text}. Nothing was changed."
        )

    eligible_watts = sum(item["wattage"] for item in eligible)
    return (
        f"Cannot turn on {target['name']} ({target['wattage']}W, priority {target['priority']}). "
        f"Load is {load}W, so it needs {need}W freed. "
        f"Worse-priority appliances that can be shed: {describe(eligible)} "
        f"({eligible_watts}W together). That is not enough. "
        f"Left untouched: {protected_text}. Nothing was changed."
    )


def result_message(lead, shed, restored, total):
    parts = [lead]
    if shed:
        parts.append(f"Shed {describe(shed)} to stay within {CAPACITY}W.")
    if restored:
        parts.append(f"Restored {describe(restored)} because there was room.")
    parts.append(f"Load is now {total}W, with {CAPACITY - total}W free.")
    return " ".join(parts)