import sqlite3
import sqlite3


def get_recent_quotes(limit=5):

    conn = sqlite3.connect("quotes.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            created_at,
            layer,
            material,
            total
        FROM quote_history
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()

    conn.close()

    return rows


def init_db():

    conn = sqlite3.connect("quotes.db")

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quote_history (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        customer_id TEXT,

        layer INTEGER,
        material TEXT,

        length_mm REAL,
        width_mm REAL,

        qty INTEGER,

        issue_ratio REAL,

        total REAL,
        unit_price REAL,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

def search_quotes(keyword, limit=10):

    conn = sqlite3.connect("quotes.db")

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            created_at,
            layer,
            material,
            total
        FROM quote_history
        WHERE
            layer LIKE ?
            OR material LIKE ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (
            f"%{keyword}%",
            f"%{keyword}%",
            limit
        )
    )

    rows = cursor.fetchall()

    conn.close()

    return rows

def get_average_price(keyword):

    conn = sqlite3.connect("quotes.db")

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            AVG(total),
            COUNT(*)
        FROM quote_history
        WHERE
            layer LIKE ?
            OR material LIKE ?
        """,
        (
            f"%{keyword}%",
            f"%{keyword}%"
        )
    )

    row = cursor.fetchone()

    conn.close()

    return row


def save_quote(customer_id, parsed, result):

    conn = sqlite3.connect("quotes.db")

    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO quote_history (

        customer_id,

        layer,
        material,

        length_mm,
        width_mm,

        qty,

        issue_ratio,

        total,
        unit_price

    )

    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

    """, (

        customer_id,

        parsed.get("layer"),
        parsed.get("material"),

        parsed.get("length_mm"),
        parsed.get("width_mm"),

        parsed.get("qty"),

        result.get("issue_ratio"),

        result.get("total"),
        result.get("unit_price")
    ))

    conn.commit()
    conn.close()