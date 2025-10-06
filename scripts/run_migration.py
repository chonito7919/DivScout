#!/usr/bin/env python3
"""Run database migration"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db_connection import db

migration_file = Path(__file__).parent.parent / 'migrations' / '001_add_company_info.sql'

with open(migration_file, 'r') as f:
    sql = f.read()

with db.get_connection() as conn:
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    print("✓ Migration completed successfully")
