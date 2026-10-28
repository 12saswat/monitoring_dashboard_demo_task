"""
SQLite Database Inspection Utility
Allows quick inspection of all tables, recorded telemetry, alerts, and application data.
"""

import sys
import sqlite3

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB_FILE = "monitoring.db"

def inspect():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    print("=" * 65)
    print("🗄️  SQLITE DATABASE INSPECTION: monitoring.db")
    print("=" * 65)

    # 1. List Tables
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in c.fetchall()]
    print(f"\n📂 Database Tables ({len(tables)}):")
    for t in tables:
        c.execute(f"SELECT COUNT(*) FROM {t}")
        count = c.fetchone()[0]
        print(f"  • {t:<25} ({count} rows)")

    # 2. Sample Users
    print("\n👥 Sample Users (from 'users' table):")
    c.execute("SELECT id, name, email, role, status FROM users LIMIT 5")
    for row in c.fetchall():
        print(f"  [{row[0]}] {row[1]:<16} | {row[2]:<26} | Role: {row[3]:<10} | Status: {row[4]}")

    # 3. Sample Products
    print("\n📦 Sample Products (from 'products' table):")
    c.execute("SELECT id, sku, name, price, stock FROM products LIMIT 5")
    for row in c.fetchall():
        print(f"  [{row[0]}] {row[1]:<15} | {row[2]:<32} | ${row[3]:<7.2f} | Stock: {row[4]}")

    # 4. Recent Telemetry Logs
    print("\n📡 Latest API Request Telemetry (from 'api_request_logs'):")
    c.execute("""
        SELECT timestamp, method, path, status_code, duration_ms, is_error 
        FROM api_request_logs 
        ORDER BY id DESC LIMIT 5
    """)
    for row in c.fetchall():
        err_badge = "❌ FAIL" if row[5] else "✅ OK"
        print(f"  {row[0]} | {row[1]:<4} {row[2]:<28} | HTTP {row[3]} ({row[4]:<6.2f} ms) | {err_badge}")

    # 5. Recent Alerts
    print("\n🚨 Latest Incident Alerts (from 'alert_logs'):")
    c.execute("""
        SELECT alert_id, severity, rule_name, title, status 
        FROM alert_logs 
        ORDER BY id DESC LIMIT 5
    """)
    alerts = c.fetchall()
    if alerts:
        for row in alerts:
            print(f"  {row[0]} | [{row[1]}] {row[2]:<28} | Status: {row[4]} | Title: {row[3]}")
    else:
        print("  (No alerts logged yet)")

    print("\n" + "=" * 65)
    conn.close()

if __name__ == "__main__":
    inspect()
