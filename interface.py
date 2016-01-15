import npyscreen
import psycopg2

## Convenience functions for accessing db data
## Could be abstracted into its own class maybe

cursor = None

def databases():
    cursor.execute('SELECT datname FROM pg_database WHERE datistemplate = false;')
    return [row[0] for row in cursor.fetchall()]

def tables():
    'Get list of tables using global cursor object'
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' and NOT table_name = 'migrate_version' ORDER BY table_name;")
    return [row[0] for row in cursor.fetchall()]

def rows(table):
    'Get rows from table using global cursor object'
    ## Table field can't be parametrized
    cursor.execute("SELECT * FROM " + table + " ORDER BY " + ', '.join(get_pk_names(table)) + ";")
    return cursor.fetchall()

def columns(table):
    'Get list of column names from table'
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s;", (table,))
    columns = [row[0] for row in cursor]
    col_list = [col.title() for col in columns]
    return col_list

def get_pk_names(table):
    'Get primary key name(s) of table'
    cursor.execute("SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) WHERE i.indrelid = '" + table + "'::regclass AND i.indisprimary;")
    return [pk[0] for pk in cursor.fetchall()]

def get_pk_for_row(table, row):
    'Get pk:value mapping for row of table'
    keys = get_pk_names(table)
    cursor.execute("SELECT {} from {} ORDER BY {};".format(
        ", ".join(keys), table, ', '.join(keys)))
    values = cursor.fetchall()[row]
    return dict(zip(keys, values))

def where_clause(pk_dict):
    'pk1_name = pk1_value AND pk2_name = pk2_value AND ... '
    clauses = ["{} = '{}'".format(key, pk_dict[key]) for key in pk_dict.keys()]
    return ' AND '.join(clauses)

def errorBox(message):
    'Display a modal dialog box'
    F = npyscreen.Popup(name='Error')
    F.add(npyscreen.FixedText, value=message)
    F.edit()

def addRow(table, parentApp):
    'Add a row to table'
    F = npyscreen.ActionForm(name='Add a row',
                             lines=15,
                             columns=40,
                             show_atx = 20,
                             show_aty = 5)
    cols = columns(table)
    values = [F.add(npyscreen.TitleText, name=col) for col in cols]

    def insert(self):
        # remove empty values
        pruned_cols = []
        pruned_values = []
        for x in zip(cols, [x.value for x in values]):
            if x[1]:
                pruned_cols.append(x[0])
                pruned_values.append("'{}'".format(x[1]))

        try:
            cursor.execute("BEGIN; INSERT INTO {} ({}) VALUES ({}); COMMIT;".format(
                table,
                ', '.join(pruned_cols),
                ', '.join(pruned_values)))
            parentApp.switchForm('INTERFACE')
        except Exception as e:
            cursor.execute("ABORT;")
            errorBox(e.message)

    funcType = type(F.on_ok)
    F.on_ok = funcType(insert, F, npyscreen.ActionForm)
    F.edit()

class connectDB(npyscreen.Form):
    def afterEditing(self):
        db_kwargs = {}
        # Present option to connect() only if value is filled in
        if self.dbHost.value: db_kwargs['host'] = self.dbHost.value
        if self.dbUser.value: db_kwargs['user'] = self.dbUser.value
        if self.dbPass.value: db_kwargs['password'] = self.dbPass.value
        db_kwargs['database'] = self.dbName.value or 'postgres'
        try:
            conn = psycopg2.connect(**db_kwargs)
            global cursor
            cursor = conn.cursor()
            self.parentApp.setNextForm("INTERFACE")
        except psycopg2.Error as e:
            npyscreen.notify_confirm(str(e), title="Connection Error", form_color='STANDOUT', wrap=True, wide=False, editw=1)

    def create(self):
        self.show_atx = 20
        self.show_aty = 5
        self.dbName = self.add(npyscreen.TitleText, name='Database Name')
        self.dbHost = self.add(npyscreen.TitleText, name='Host')
        self.dbUser = self.add(npyscreen.TitleText, name='User')
        self.dbPass = self.add(npyscreen.TitlePassword, name='Password')

class DumpTable(npyscreen.ActionForm):
    def create(self):
        self.show_atx = 20
        self.show_aty = 5
        self.filename = self.add(npyscreen.TitleFilename, name = 'Filename:')

    def on_ok(self):
        table = self.parentApp.getForm('INTERFACE').current_table
        try:
            filename = self.filename.value
            with open(filename, 'w') as f:
                cursor.copy_to(f, table)
                self.filename.value = ''
                npyscreen.notify_confirm('Table data dumped to "{}"'.format(filename), title="Success", form_color='STANDOUT', wrap=True, wide=False, editw=1)
        except Exception as e:
            errorBox(e.message)
        self.parentApp.switchForm('INTERFACE')

    def on_cancel(self):
        cursor.execute("ABORT;")
        self.parentApp.switchForm('INTERFACE')

class LoadTable(npyscreen.ActionForm):
    def create(self):
        self.show_atx = 20
        self.show_aty = 5
        self.filename = self.add(npyscreen.TitleFilename, name = 'Filename:')

    def on_ok(self):
        table = self.parentApp.getForm('INTERFACE').current_table
        try:
            filename = self.filename.value
            with open(filename, 'r') as f:
                cursor.copy_from(f, table)
                self.filename.value = ''
                npyscreen.notify_confirm('Table data loaded from "{}"'.format(filename), title="Success", form_color='STANDOUT', wrap=True, wide=False, editw=1)
        except Exception as e:
            errorBox(e.message)
        self.parentApp.switchForm('INTERFACE')

    def on_cancel(self):
        cursor.execute("ABORT;")
        self.parentApp.switchForm('INTERFACE')

class EditForm(npyscreen.ActionForm):
    def create(self):
        self.show_atx = 20
        self.show_aty = 5
        self.new_value = self.add(npyscreen.TitleText, name = 'New value:')
	
    def on_ok(self):
        table = self.parentApp.getForm('INTERFACE').current_table
        row = self.parentApp.getForm('INTERFACE').mainScreen.edit_cell[0]
        col = self.parentApp.getForm('INTERFACE').mainScreen.edit_cell[1]
        col_title = self.parentApp.getForm('INTERFACE').mainScreen.col_titles[col].lower()
        row_to_change = self.parentApp.getForm('INTERFACE').mainScreen.values[row]
        val_to_change = row_to_change[col]
        pk_dict = get_pk_for_row(table, row)

        #update field
        try:
            cursor.execute('BEGIN; UPDATE ' + table + ' SET ' + col_title + " = '" + self.new_value.value + "' WHERE " + where_clause(pk_dict) + "; COMMIT;")
            self.new_value.value = ''
            self.parentApp.switchForm('INTERFACE')
        except Exception as e:
            errorBox(e.message)

    def on_cancel(self):
        cursor.execute("ABORT;")
        self.parentApp.switchForm('INTERFACE')

class DeleteForm(npyscreen.ActionForm):
    def create(self):
        self.show_atx = 20
        self.show_aty = 5
        self.add(npyscreen.FixedText, value = "Delete row?")

    def on_ok(self):
        table = self.parentApp.getForm('INTERFACE').current_table
        row = self.parentApp.getForm('INTERFACE').mainScreen.edit_cell[0]
        pk_dict = get_pk_for_row(table, row)

        # delete the row
        try:
            cursor.execute('BEGIN; DELETE FROM {} WHERE {}; COMMIT;'.format(
                table, where_clause(pk_dict)))
            self.parentApp.switchForm('INTERFACE')
        except Exception as e:
            errorBox(e.message)

    def on_cancel(self):
        cursor.execute('ABORT;')
        self.parentApp.switchForm('INTERFACE')

class MainForm(npyscreen.ActionForm, npyscreen.FormWithMenus):
    def create(self):
        self.tables = self.add(npyscreen.TitleMultiLine,
                               max_height = 5,
                               max_width = 20,
                               begin_entry_at = 0,
                               name = 'Tables',
                               values = [],
                               scroll_exit = False,
                               select_exit = True,
        )
        self.nextrelx = 30
        self.nextrely = 2
        self.mainScreen = self.add(npyscreen.GridColTitles, npyscreen.MultiLineAction,
                               name = 'Rows',
        )
        self.menu = self.new_menu(name = 'Table Actions')
        self.menu.addItem('Dump Table', self.press_1, '1')
        self.menu.addItem('Load Table', self.press_2, '2')

        self.menu = self.new_menu(name = 'Row Actions')
        self.menu.addItem('Edit Selected Value', self.press_3, '3')
        self.menu.addItem('Add Row', self.press_4, '4')
        self.menu.addItem('Delete Row', self.press_5, '5')

    def press_1(self):
        #user will be sent to DumpTable form
        self.parentApp.switchForm('DUMP_TABLE')
 
    def press_2(self):
        #user will be sent to LoadTable form
        self.parentApp.switchForm('LOAD_TABLE')
 
    def press_3(self):
        self.parentApp.switchForm('EDIT_VALUE')
    
    def press_4(self):
        #user will be sent to AddRow form
        addRow(self.current_table, self.parentApp)
 
    def press_5(self):
        #user will be sent to DeleteRow form
        self.parentApp.switchForm('DELETE_ROW')

    def while_editing(self, *args):
        # update table list
        self.tables.values = tables()
        self.tables.display()

        #update main display
        try:
            self.current_table = self.tables.values[self.tables.value]
            self.mainScreen.col_titles = columns(self.current_table)
            self.mainScreen.values = rows(self.current_table)
        except:
            self.mainScreen.values = []

        self.mainScreen.edit_cell = [0, 0]
        self.mainScreen.display()
        self.display()

    def on_cancel(self):
        self.parentApp.switchForm(None)


class DB_UI(npyscreen.NPSAppManaged):
    def onStart(self):
        self.addForm('MAIN', connectDB,
                     lines=10,
                     columns=40,
                     name='Connect to Database'
        )
        self.addForm('DUMP_TABLE', DumpTable,
                     lines=10,
                     columns=40,
                     name='DumpTable'
        )
        self.addForm('LOAD_TABLE', LoadTable,
                     lines=10,
                     columns=40,
                     name='LoadTable'
        )
        self.addForm('EDIT_VALUE', EditForm,
                     lines=10,
                     columns=40,
                     name='EditForm'
        )
        self.addForm('DELETE_ROW', DeleteForm,
                     lines=10,
                     columns=40,
                     name='DeleteForm')
        self.addForm('INTERFACE', MainForm)

if __name__ == '__main__':
    UI = DB_UI()
    UI.run()
