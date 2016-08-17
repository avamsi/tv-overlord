import os
import sys
import platform
import configparser
import shutil
import sqlite3
import click
import shlex
import pathlib
from types import SimpleNamespace as SN
from pprint import pprint as pp


def message(msg, filename):
    click.secho(msg, bold=True)
    click.secho('  %s' % filename, fg='green')
    return True


class ConfigBuilder:
    is_win = True if platform.system() == 'Windows' else True

    def __init__(self, dir_name):
        self.dir_name = dir_name
        self.user_home = None
        self.user_config = None
        self.app_config = None
        self.user_db = None
        self.oldfields = None

    def create_config_dir(self):
        """Create the config dir

        Create it in the default location for the users platform and
        only if it doesn't already exist.
        """
        dir_path = click.get_app_dir(self.dir_name)
        dir_path = pathlib.Path(dir_path)
        self.user_home = dir_path
        if not dir_path.exists():
            dir_path.mkdir(parents=True)
            return True
        else:
            return False

    def create_config(self, config_name):
        """Ensure that the config file exists

        :param config_name: Name of config file
        """
        self.user_config = self.user_home / config_name

        app_home = pathlib.Path(__file__).parent
        self.app_config = app_home / config_name

        if not self.user_config.exists():
            self.write_config()
            # shutil.copy(str(self.app_config), str(self.user_home))
            return True
        else:
            return False

    def write_config(self):
        # this will write the text file with the correct line endings
        # for the platform
        with self.app_config.open() as source, \
             self.user_config.open('w') as dest:
            for line in source:
                dest.write(line)

    def create_modify_db(self, db_name, sqldata):
        """Create the DB is it doesn't exist"""

        self.user_db = self.user_home / db_name
        if not self.user_db.exists():
            sql = self.generate_tables(sqldata)
            self.new_db(sql)
            return True
        else:
            modified = False
            for table in sqldata:
                if self.table_changed(table):
                    self.update_db(table)
                    modified = True
            return modified

    def generate_table(self, table):
        sql = ['CREATE TABLE %s (' % table['name']]
        fieldsa = []
        for field in table['fields']:
            fieldsa.append('    %s %s' % (field[0], field[1]))
        fields = ',\n'.join(fieldsa)
        sql.append(fields)
        sql.append(');')
        sql = '\n'.join(sql)
        return sql

    def generate_tables(self, sqldata):
        tables = []
        for table in sqldata:
            tables.append(self.generate_table(table))
        sql = '\n'.join(tables)
        return sql

    def table_changed(self, table):
        conn = sqlite3.connect(str(self.user_db))
        sql = 'SELECT * from %s;' % table['name']
        curs = conn.execute(sql)
        self.oldfields = {f[0] for f in curs.description}
        newfields = {f[0] for f in table['fields']}
        return self.oldfields != newfields

    def update_db(self, table):
        backupname = 'backup_%s' % table['name']

        backupsql = 'ALTER TABLE %s RENAME TO %s;' % (
            table['name'], backupname)
        newtable = self.generate_table(table)
        fieldnames = ',\n'.join(self.oldfields)
        copydata = 'INSERT INTO %s (%s) SELECT %s FROM %s;' % (
            table['name'], fieldnames, fieldnames, backupname)
        delbackup = 'DROP TABLE %s;' % backupname

        conn = sqlite3.connect(str(self.user_db))
        conn.isolation_level = None
        curs = conn.cursor()
        try:
            curs.execute('BEGIN')
            curs.execute(backupsql)
            curs.execute(newtable)
            curs.execute(copydata)
            curs.execute(delbackup)
            curs.execute('COMMIT')
        except conn.Error as e:
            click.echo('Database update failed')
            click.echo(', '.join(e.args))
            curs.execute('ROLLBACK')
            sys.exit(1)

    def new_db(self, sql):
        conn = sqlite3.connect(str(self.user_db))
        conn.executescript(sql)
        conn.commit()
        conn.close()


class Config:
    def __init__(self):
        pass

    is_win = False
    if platform.system() == 'Windows':
        is_win = True

    thetvdb_apikey = 'DFDB0A667C844513'
    use_cache = True

    console_columns, console_rows = click.get_terminal_size()
    console_columns = int(console_columns)
    if is_win:
        # On windows, columns are 1 char too wide
        console_columns = console_columns - 1

    # progressbar settings
    pb = SN()
    pb.width = 50
    if console_columns < 90:
        pb.width = 30
    if console_columns < 80:
        pb.width = 20
    if is_win:
        pb.light = 'green'
        pb.dark = 'blue'
    else:
        pb.light = 35
        pb.dark = 23
    pb.empty_char = ' '
    pb.fill_char = '*'
    pb.template = '%(label)s %(bar)s %(info)s'

    if is_win:
        color = SN()
        color.table = SN(
            title=SN(fg='white', bg='green'),
            header=SN(fg='white', bg='blue'),
            body=SN(fg='white', bg=None),
            bar=SN(fg='green', bg=None),
            hidef=SN(fg='green', bg=None),
        )
        color.info = SN(
            links=SN(fg='blue', bg=None),
            ended=SN(fg='red', bg=None),
            last=SN(fg='cyan', bg=None),
            future=SN(fg='green', bg=None),
        )
        color.calendar = SN(
            header=SN(fg='white', bg='blue'),
            dates=SN(fg='white', bg=None),
            titles=SN(fg='white', bg=None),
            altdates=SN(fg='white', bg='blue'),
            alttitles=SN(fg='white', bg='blue'),
        )
        color.missing = SN(fg='green', bg=None)
        color.edit = SN(fg='yellow', bg='black')
        color.warn = SN(fg='yellow', bg='black')
    else:
        color = SN()
        color.table = SN(
            title=SN(fg=None, bg=19),
            header=SN(fg=None, bg=17),
            body=SN(fg='white', bg=None),
            bar=SN(fg=19, bg=None),
            hidef=SN(fg=76, bg=None),
        )
        color.info = SN(
            links=SN(fg=20, bg=None),
            ended=SN(fg='red', bg=None),
            last=SN(fg=48, bg=None),
            future=SN(fg=22, bg=None),
        )
        color.calendar = SN(
            header=SN(fg='white', bg=17),
            dates=SN(fg='white', bg=None),
            titles=SN(fg='white', bg=None),
            altdates=SN(fg='white', bg=17),
            alttitles=SN(fg='white', bg=18),
        )
        color.missing = SN(fg='green', bg=None)
        color.edit = SN(fg='yellow', bg='black')
        color.warn = SN(fg='yellow', bg='black')

    # number of ip address octets to match to be considered ok.  Must
    # be between 1 and 4
    parts_to_match = 3

    # create files
    files_created = False
    user_config_dir = 'tvoverlord'
    cb = ConfigBuilder(user_config_dir)

    if cb.create_config_dir():
        files_created = message('App config dir created:', cb.user_home)

    if cb.create_config('config.ini'):
        files_created = message(
            '%s created:' % cb.user_config.name, cb.user_config)

    user_config = str(cb.user_config)
    user_dir = str(cb.user_home)

    sql = [
        {
            'name': 'shows',
            'fields': [
                ['id', 'INTEGER PRIMARY KEY AUTOINCREMENT'],
                ['name', 'TEXT'],
                ['search_engine_name', 'TEXT'],
                ['display_name', 'TEXT'],
                ['date_added', 'TEXT'],
                ['network_status', 'TEXT'],
                ['status', 'TEXT'],
                ['thetvdb_series_id', 'TEXT'],
                ['ragetv_series_id', 'TEXT'],
                ['imdb_series_id', 'TEXT'],
                ['alt_series_id', 'TEXT'],
                ['season', 'NUMERIC'],
                ['episode', 'NUMERIC'],
                ['next_episode', 'TEXT'],
                ['airs_time', 'TEXT'],
                ['airs_dayofweek', 'TEXT'],
                ['rating', 'TEXT'],
                ['auto_download', 'TEXT'],
                ['notes', 'TEXT'],
            ],
        },
        {
            'name': 'tracking',
            'fields': [
                ['download_date', 'TEXT'],
                ['show_title', 'TEXT'],
                ['season', 'TEXT'],
                ['episode', 'TEXT'],
                ['download_data', 'TEXT'],
                ['chosen', 'TEXT'],
                ['chosen_hash', 'TEXT'],
                ['one_off', 'INTERGER'],
                ['complete', 'INTERGER'],
                ['filename', 'TEXT'],
                ['destination', 'TEXT'],
            ]
        }
    ]
    if cb.create_modify_db('shows.sqlite3', sql):
        files_created = message(
            'Database has been created/updated:', cb.user_db)

    if files_created:
        click.echo('-' * console_columns)
        click.echo()

    db_file = str(cb.user_db)

    categories = SN()
    categories.resolution = [
        '1080p', '1080i', '720p', '720i', 'hr', '576p',
        '480p', '368p', '360p']
    categories.sources = [
        'bluray', 'remux', 'dvdrip', 'webdl', 'hdtv', 'bdscr',
        'dvdscr', 'sdtv', 'webrip', 'dsr', 'tvrip', 'preair',
        'ppvrip', 'hdrip', 'r5', 'tc', 'ts', 'cam', 'workprint']
    categories.codecs = [
        '10bit', 'h265', 'h264', 'x264', 'xvid', 'divx']
    categories.audio = [
        'truehd', 'dts', 'dtshd', 'flac', 'ac3', 'dd5.1', 'aac', 'mp3']

    cfg = configparser.ConfigParser(allow_no_value=True, interpolation=None)
    cfg.read(str(cb.user_config))

    # Settings from config.ini ---------------------------------
    # [App Settings]
    try:
        ip = cfg.get('App Settings', 'ip whitelist')
        # split, strip, and remove empty values from whitelist
        ip = [i.strip() for i in ip.split(',') if i.strip()]
    except configparser.NoOptionError:
        ip = None

    try:
        email = cfg.get('App Settings', 'email')
    except configparser.NoOptionError:
        email = False

    try:
        single_file = True if cfg.get(
            'App Settings', 'single file') == 'yes' else False
    except configparser.NoOptionError:
        single_file = False

    try:
        template = cfg.get('App Settings', 'template')
    except configparser.NoOptionError:
        template = False

    try:
        search_type = 'nzb' if cfg.get(
            'App Settings', 'search type') == 'nzb' else 'torrent'
    except configparser.NoOptionError:
        search_type = 'torrent'

    try:
        client = cfg.get('App Settings', 'client')
        client = shlex.split(client)
    except configparser.NoOptionError:
        client = None

    try:
        magnet_dir = cfg.get('App Settings', 'magnet folder')
    except configparser.NoOptionError:
        magnet_dir = None

    # [File Locations]
    try:
        tv_dir = os.path.expanduser(cfg.get('File Locations', 'tv dir'))
    except configparser.NoOptionError:
        tv_dir = None
    try:
        staging = os.path.expanduser(cfg.get('File Locations', 'staging'))
    except configparser.NoOptionError:
        staging = None


if __name__ == '__main__':
    c = Config()
    click.echo(c.staging)
    pass
