import os
import sqlite3
import json

from .. import WORK_DIR

db_path = os.path.join(WORK_DIR, 'example.db')


def list_collection(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('SELECT id,name FROM folder where parent_id=0')
    data = [{'id': item[0], 'name': item[1]} for item in cur.fetchall()]
    con.close()
    return data


def create_collection(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('INSERT INTO folder(name) VALUES (?)', (kwargs['name'],))
    inserted_id = cur.lastrowid
    con.commit()
    con.close()
    return inserted_id


def delete_collection(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('DELETE FROM folder where id=?', (kwargs['id'],))
    con.commit()
    con.close()
    return True


def list_folder(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('SELECT id,name FROM folder where parent_id=?', (kwargs['parent_id'],))
    data = [{'id': item[0], 'name': item[1]} for item in cur.fetchall()]
    con.close()
    return data


def create_folder(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('INSERT INTO folder(name,parent_id,description,pre_script,post_script) VALUES (?,?,?,?,?)', (
        kwargs.get('name','New Folder'),
        kwargs.get('parent_id', 0),
        kwargs.get('description', ''),
        kwargs.get('pre_script',''),
        kwargs.get('post_script',''),
    ))
    inserted_id = cur.lastrowid
    con.commit()
    con.close()
    return inserted_id


def retrieve_folder(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('SELECT id,name,description,pre_script,post_script,parent_id FROM folder where id=?', (kwargs['id'],))
    bean = cur.fetchone()
    con.close()
    return {'id': bean[0],
            'name': bean[1],
            'description': bean[2],
            'pre_script': bean[3],
            'post_script': bean[4],
            'parent_id': bean[5]}


def update_folder(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    keys = list(sorted(kwargs.keys()))
    var = ','.join([f'{key}=?' for key in keys if key != 'id'])
    sqlstr = f'UPDATE folder SET {var},modified_at=current_date WHERE id=?'
    values = [kwargs[key] for key in keys if key != 'id']
    values.append(kwargs['id'])
    cur.execute(sqlstr, values)
    con.commit()
    con.close()
    return True


def delete_folder(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('DELETE FROM folder where id=?', (kwargs['id'],))
    con.commit()
    con.close()
    return True


def list_request(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('SELECT id,name,method FROM request where folder_id=?', (kwargs['folder_id'],))
    items = cur.fetchall()
    con.close()
    return [{'id': item[0], 'name': item[1], 'method': item[2]} for item in items]


def create_request(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        'INSERT INTO request(name,method,url,params,headers,body,auth,pre_script,post_script,folder_id) VALUES (?,?,?,?,?,?,?,?,?,?)',
        (kwargs.get('name', 'New Request'),
         kwargs.get('method', 'GET'),
         kwargs.get('url',''),
         json.dumps(kwargs.get('params',{})),
         json.dumps(kwargs.get('headers',{})),
         json.dumps(kwargs.get('body',{})),
         json.dumps(kwargs.get('auth',{})),
         kwargs.get('pre_script', ''),
         kwargs.get('post_script', ''),
         kwargs.get('folder_id', 0)))
    inserted_id = cur.lastrowid
    con.commit()
    con.close()
    return inserted_id


def retrieve_request(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('SELECT id,name,pre_script,post_script,params,headers,body,auth,method,url FROM request where id=?', (kwargs['id'],))
    data = cur.fetchone()
    con.close()
    return {'id': data[0],
            'name': data[1],
            'pre_script': data[2],
            'post_script':data[3],
            'params': json.loads(data[4]),
            'headers': json.loads(data[5]),
            'body': json.loads(data[6]),
            'auth': json.loads(data[7]),
            'method':data[8],
            'url':data[9]}


def update_request(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    keys = list(sorted(kwargs.keys()))
    var = ','.join([f'{key}=?' for key in keys if key != 'id'])
    sqlstr = f'UPDATE request SET {var},modified_at=current_date WHERE id=?'
    values = [kwargs[key] for key in keys if key != 'id']
    values.append(kwargs['id'])
    cur.execute(sqlstr, values)
    con.commit()
    con.close()
    return


def delete_request(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('DELETE FROM request where id=?', (kwargs['id'],))
    con.commit()
    con.close()
    return


def list_album(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('SELECT id,name,is_active FROM album')
    items = cur.fetchall()
    con.close()
    return [{'id': item[0], 'name': item[1], 'is_active': item[2]} for item in items]


def create_album(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('INSERT INTO album(name) VALUES (?)', (kwargs['name'],))
    inserted_id = cur.lastrowid
    con.commit()
    con.close()
    return inserted_id


def update_album(*args, **kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('UPDATE album SET name=?,modified_at=current_date WHERE id=?', (kwargs['name'], kwargs['id'],))
    con.commit()
    con.close()
    return True


def active_album(*args, **kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("update album set is_active=0 where name!='Globals' and is_active=1")
    cur.execute("update album set is_active=1 where id=?", (kwargs['id'],))
    con.commit()
    con.close()
    return True


def delete_album(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("DELETE FROM variable where belong_name='album' and belong_id=?", (kwargs['id'],))
    cur.execute('DELETE FROM album where id=?', (kwargs['id'],))
    con.commit()
    con.close()
    return True


def list_variable(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('SELECT id,name,content FROM variable where belong_name=? and belong_id=?',
                (kwargs['belong_name'], kwargs['belong_id']))
    items = cur.fetchall()
    con.close()
    return [{'id': item[0], 'name': item[1], 'content': item[2]} for item in items]


def retrieve_global_variable(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("select id,name from album where name='Globals'")
    album = cur.fetchone()
    if album is None:
        con.close()
        return None

    cur.execute('SELECT id,name,content FROM variable where belong_name=? and belong_id=? and name=?',
                ('album', album[0], kwargs['name']))
    item = cur.fetchone()
    if item is not None:
        con.close()
        return item[2]

    con.close()
    return None


def retrieve_active_variable(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    cur.execute("select id,name from album where name!='Globals' and is_active=1")
    album = cur.fetchone()
    if album is None:
        con.close()
        return None

    cur.execute('SELECT id,name,content FROM variable where belong_name=? and belong_id=? and name=?',
                ('album', album[0], kwargs['name']))
    item = cur.fetchone()
    if item is None:
        cur.execute("select id,name from album where name='Globals'")
        album = cur.fetchone()
        if album is not None:
            cur.execute('SELECT id,name,content FROM variable where belong_name=? and belong_id=? and name=?',
                        ('album', album[0], kwargs['name']))
            item = cur.fetchone()
            if item is not None:
                con.close()
                return item[2]
        con.close()
        return None
    con.close()
    return item[2]


def retrieve_folder_variable(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('SELECT id,name,content FROM variable where belong_name=? and belong_id=? and name=?',
                ('folder', kwargs['folder_id'], kwargs['name']))
    item = cur.fetchone()
    if item is not None:
        con.close()
        return item[2]

    con.close()
    return None


def create_variable(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('INSERT INTO variable(name,content,belong_name,belong_id) values (?,?,?,?)',
                (kwargs['name'], kwargs['content'], kwargs['belong_name'], kwargs['belong_id']))
    inserted_id = cur.lastrowid
    con.commit()
    con.close()
    return inserted_id


def update_variable(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('UPDATE variable SET name=?,content=?,modified_at=current_date WHERE id=?',
                (kwargs['name'], kwargs['content'], kwargs['id']))
    con.commit()
    con.close()
    return True


def delete_variable(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('DELETE FROM variable where id=?', (kwargs['id'],))
    con.commit()
    con.close()
    return True


def list_history(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('SELECT id,method,url FROM history')
    items = cur.fetchall()
    data = [{'id': item[0], 'method': item[1], 'url': item[2]} for item in items]
    con.close()
    return data


def create_history(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        'INSERT INTO history(method,url,params,headers,body,auth,pre_script,post_script,res_body,res_headers,res_cookies) values (?,?,?,?,?,?,?,?,?,?,?)',
        (kwargs['method'],
         kwargs['url'],
         kwargs['params'],
         kwargs['headers'],
         kwargs['body'],
         kwargs['auth'],
         kwargs['pre_script'],
         kwargs['post_script'],
         kwargs['res_body'],
         kwargs['res_headers'],
         kwargs['res_cookies']))
    inserted_id = cur.lastrowid
    con.commit()
    con.close()
    return inserted_id


def retrieve_history(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        'select id,method,url,params,headers,body,auth, pre_script,post_script,res_body,res_headers,res_cookies from history where id=?',
        (kwargs['id'],))
    data = cur.fetchone()
    con.commit()
    con.close()
    if data is None:
        return None
    return {'id': data[0],
            'method': data[1],
            'url': data[2],
            'params': data[3],
            'headers': data[4],
            'body': data[5],
            'auth': data[6],
            'pre_script': data[7],
            'post_script': data[8],
            'res_body': data[9],
            'res_headers': data[10],
            'res_cookies': data[11]}


def delete_history(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('DELETE FROM history where id=?', (kwargs['id'],))
    con.commit()
    con.close()
    return True


def delete_all_history(**kwargs):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute('DELETE FROM history where id>0')
    con.commit()
    con.close()
    return True
