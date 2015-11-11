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
    cursor.execute("SELECT * FROM " + table)
    return cursor.fetchall()

def columns(table):
    'Get list of column names from table'
    # Get column names
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s;", (table,))
    columns = [row[0] for row in cursor]
    col_list = [col.title() for col in columns]
    return col_list

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

class MainForm(npyscreen.FormWithMenus):
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
        self.mainScreen = self.add(npyscreen.GridColTitles, 
                               name = 'Rows',
        )
        self.menu = self.new_menu(name = 'Table Actions')
        self.menu.addItem('Add Table', self.press_1, '1')
        self.menu.addItem('Delete Selected Table', self.press_2, '2')

        self.menu = self.new_menu(name = 'Row Actions')
        self.menu.addItem('Edit Selected Value', self.press_3, '3')
        self.menu.addItem('Add Row', self.press_4, '4')
        self.menu.addItem('Delete Row', self.press_5, '5')

    def press_1(self):
        npyscreen.notify_ok_cancel('User will enter new table info here.', 'Add Table', editw = 1)

    def press_2(self):
        npyscreen.notify_ok_cancel('User will be asked to confirm table deletion here.', 'Delete Table', editw = 1)

    def press_3(self):
        npyscreen.notify_ok_cancel('User will enter new value here.', 'Edit Selected Value', editw = 1)

    def press_4(self):
        npyscreen.notify_ok_cancel('User will enter new row info here.', 'Add Row', editw = 1)

    def press_5(self):
        npyscreen.notify_ok_cancel('User will be asked to confirm row deletion here.', 'Delete Row', editw = 1)

    def while_editing(self, *args):
        # update table list
        self.tables.values = tables()
        self.tables.display()

        #update main display
        try:
            table = self.tables.values[self.tables.value]
            self.mainScreen.col_titles = columns(table)
            self.mainScreen.values = rows(table)
            self.mainScreen.edit_cell = 0
        except:
            self.mainScreen.values = []

        self.mainScreen.display()
        self.display()

    def afterEditing(self):
        self.parentApp.setNextForm('MAIN')
        
    def actionHighlighted(self, act_on_this, key_press):
        pass
class DB_UI(npyscreen.NPSAppManaged):
    def onStart(self):
        self.addForm('MAIN', connectDB,
                     lines=10,
                     columns=40,
                     name='Connect to Database'
        )
        self.addForm('INTERFACE', MainForm)

if __name__ == '__main__':
    UI = DB_UI()
    UI.run()
