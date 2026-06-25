import os
import sqlite3

from .. import WORK_DIR


def start_event():
    db_path = os.path.join(WORK_DIR, 'example.db')
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # 初始化数据库
    cur.execute('''CREATE TABLE IF NOT EXISTS folder (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT NOT NULL,
description TEXT DEFAULT '',
pre_script TEXT DEFAULT '',
post_script TEXT DEFAULT '',
parent_id INTEGER DEFAULT 0,
create_at DATETIME DEFAULT CURRENT_DATE,
modified_at DATETIME DEFAULT CURRENT_DATE
)''')

    cur.execute('''CREATE TABLE IF NOT EXISTS request (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT NOT NULL,
method TEXT DEFAULT 'GET',
url TEXT DEFAULT '',
params TEXT DEFAULT '{}',
headers TEXT DEFAULT '{}',
body TEXT DEFAULT '{}',
auth TEXT DEFAULT '{}',
pre_script TEXT DEFAULT '',
post_script TEXT DEFAULT '',
folder_id INTEGER DEFAULT 0,
create_at DATETIME DEFAULT CURRENT_DATE,
modified_at DATETIME DEFAULT CURRENT_DATE
)''')

    cur.execute('''CREATE TABLE IF NOT EXISTS album (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT NOT NULL,
description text DEFAULT '',
is_active BLOB DEFAULT 0,
create_at DATETIME DEFAULT CURRENT_DATE,
modified_at DATETIME DEFAULT CURRENT_DATE
)''')

    cur.execute('''CREATE TABLE IF NOT EXISTS variable (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT NOT NULL,
content TEXT DEFAULT '',
belong_name INTEGER DEFAULT '',
belong_id INTEGER DEFAULT 0,
create_at DATETIME DEFAULT CURRENT_DATE,
modified_at DATETIME DEFAULT CURRENT_DATE
)''')

    cur.execute('''CREATE TABLE IF NOT EXISTS history (
id INTEGER PRIMARY KEY AUTOINCREMENT,
method TEXT DEFAULT 'GET',
url TEXT DEFAULT '',
params TEXT DEFAULT '{}',
auth TEXT DEFAULT '{}',
headers TEXT DEFAULT '{}',
body TEXT DEFAULT '{}',
pre_script TEXT DEFAULT '',
post_script TEXT DEFAULT '',
res_body TEXT DEFAULT '',
res_headers TEXT DEFAULT '',
res_cookies TEXT DEFAULT '',
create_at DATETIME DEFAULT CURRENT_DATE,
modified_at DATETIME DEFAULT CURRENT_DATE
)''')

    cur.execute('''CREATE TABLE IF NOT EXISTS flow (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT NOT NULL,
	description TEXT DEFAULT '',
	create_at DATETIME DEFAULT CURRENT_DATE,
	modified_at DATETIME DEFAULT CURRENT_DATE
	)''')

    cur.execute('''CREATE TABLE IF NOT EXISTS flow_node (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	flow_id INTEGER NOT NULL,
	node_type TEXT NOT NULL,
	label TEXT DEFAULT '',
	x REAL DEFAULT 100.0,
	y REAL DEFAULT 100.0,
	width REAL DEFAULT 160.0,
	height REAL DEFAULT 80.0,
	config TEXT DEFAULT '{}',
	create_at DATETIME DEFAULT CURRENT_DATE,
	modified_at DATETIME DEFAULT CURRENT_DATE,
	FOREIGN KEY (flow_id) REFERENCES flow(id) ON DELETE CASCADE
	)''')

    cur.execute('''CREATE TABLE IF NOT EXISTS flow_connection (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	flow_id INTEGER NOT NULL,
	source_node_id INTEGER NOT NULL,
	source_port TEXT DEFAULT 'output',
	target_node_id INTEGER NOT NULL,
	target_port TEXT DEFAULT 'input',
	create_at DATETIME DEFAULT CURRENT_DATE,
	FOREIGN KEY (flow_id) REFERENCES flow(id) ON DELETE CASCADE,
	FOREIGN KEY (source_node_id) REFERENCES flow_node(id) ON DELETE CASCADE,
	FOREIGN KEY (target_node_id) REFERENCES flow_node(id) ON DELETE CASCADE
	)''')

    cur.execute('''CREATE TABLE IF NOT EXISTS flow_execution (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	flow_id INTEGER NOT NULL,
	status TEXT DEFAULT 'pending',
	result TEXT DEFAULT '{}',
	started_at DATETIME DEFAULT CURRENT_DATE,
	finished_at DATETIME,
	FOREIGN KEY (flow_id) REFERENCES flow(id) ON DELETE CASCADE
	)''')

    cur.execute("select * from album where name='Globals'")
    if len(cur.fetchall()) == 0:
        cur.execute("INSERT INTO album (name,is_active) VALUES ('Globals',0)")
        con.commit()

    con.commit()
    con.close()

def stop_event():
    pass
