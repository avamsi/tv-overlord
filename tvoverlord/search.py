import sys
import subprocess
import os
import platform
import concurrent.futures
from pprint import pprint as pp
import socket
# from urllib.parse import urlparse
import urllib
import time
import click

from tvoverlord.config import Config
from tvoverlord.util import U
from tvoverlord.tvutil import style, sxxexx

# torrent search engings
from tvoverlord.search_providers import extratorrent
from tvoverlord.search_providers import bitsnoop
# from tvoverlord.search_providers import kickass_to
from tvoverlord.search_providers import thepiratebay_sx
from tvoverlord.search_providers import onethreethreesevenx_to
# from tvoverlord.search_providers import torrentdownloads_me
from tvoverlord.search_providers import rarbg_to
from tvoverlord.search_providers import eztv_ag
from tvoverlord.search_providers import btstorr_cc

# newsgroup search engines
from tvoverlord.search_providers import nzbclub_com
from tvoverlord.search_providers import nzbindex_com


class SearchError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class Search(object):
    torrent_engines = [bitsnoop, extratorrent, thepiratebay_sx, btstorr_cc,
                       onethreethreesevenx_to, rarbg_to, eztv_ag]
    # , torrentdownloads_me # <-- a suspicious number of seeds

    # for nzb searches, only the first one listed will be used
    newsgroup_engines = [nzbclub_com]
    # , nzbindex_com # <-- rss feed not working

    def __init__(self):
        self.season = ''
        self.episode = ''
        self.show_name = ''
        self.se_order = []

    def job(self, engine, search_string, season, episode):
        search = engine.Provider()
        search_results = search.search(search_string, season, episode)

        # for info about each search
        # click.echo('%s -- %s' % (search.name, len(search_results)))
        self.se_order.append(search.name)
        return search_results + [search.name]

    def test_each(self, search_string):
        engines = self.torrent_engines + self.newsgroup_engines
        indent = '  '
        click.echo('Searching for: %s' % search_string)
        for engine in engines:
            search = engine.Provider()
            name = '%s (%s)' % (search.name, search.shortname)
            click.echo(style(name, bold=True))

            results = search.search(search_string)

            click.echo(indent + style(search.url, fg='blue', ul=True))
            results_count = str(len(results))
            if results_count == '0':
                results_count = style(results_count, fg='red')
            else:
                results_count = style(results_count, fg='green')
            click.echo(indent + 'Search results: %s' % results_count)

    def search(self, search_string, season=False,
               episode=False, search_type='torrent'):
        """
        Return an array of values:

        [
          [
            ['Title string', 'search url'],
            [head1, head2, head3, id],
            [head1-width, head2-width, head3-width],
            [head1-alignment, head2-alignment, head3-alignment]
          ],
          [
            [<column 1 data>, <column 2 data>, <column 3 data>, <id>],
            [<column 1 data>, <column 2 data>, <column 3 data>, <id>],
            # etc...
          ]
        ]
        """

        self.season = season
        self.episode = episode
        self.show_name = search_string
        self.search_type = search_type

        click.echo()

        if self.search_type == 'torrent':
            header = [
                [search_string, ''],
                ['Name', 'Size', 'Date', 'Seeds', 'SE'],
                [0, 10, 12, 6, 2],
                ['<', '>', '<', '>', '<']]
        else:
            header = [
                [search_string, ''],
                ['Name', 'Size', 'Date', 'SE'],
                [0, 10, 12, 2],
                ['<', '>', '<', '<']]

        if self.search_type == 'torrent':
            engines = self.torrent_engines
        elif self.search_type == 'nzb':
            engines = self.newsgroup_engines
        else:
            raise ValueError('search_type can only be "torrent" or "nzb"')

        socket.setdefaulttimeout(3.05)
        episodes = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            res = {
                executor.submit(
                    self.job, engine, search_string, season, episode
                ): engine for engine in engines
            }
            with click.progressbar(
                    concurrent.futures.as_completed(res),
                    label=U.style('  %s' % search_string, bold=True),
                    empty_char=style(Config.pb.empty_char,
                                     fg=Config.pb.dark,
                                     bg=Config.pb.dark),
                    fill_char=style(Config.pb.fill_char,
                                    fg=Config.pb.light,
                                    bg=Config.pb.light),
                    length=len(engines),
                    show_percent=False,
                    show_eta=False,
                    item_show_func=self.progress_title,
                    width=Config.pb.width,
                    bar_template=Config.pb.template,
                    show_pos=True,
            ) as bar:
                for future in bar:
                    results = future.result()
                    # remove the search engine name from the end of
                    # the results array that was added in self.job()
                    # so progress_title() could make use of it.
                    results = results[:-1]
                    episodes = episodes + results

        # go up 3 lines to remove the progress bar
        click.echo('[%sA' % 3)

        if self.search_type == 'torrent':
            self.sort_torrents(episodes)

        # return search_results
        return [header] + [episodes]

    def sort_torrents(self, episodes):
        # sort by seeds
        episodes.sort(key=lambda x: int(x[3]), reverse=True)

        # Remove torrents with 0 seeds
        for i, episode in enumerate(episodes):
            seeds = int(episode[3])
            # click.echo(episode[0])
            if not seeds:
                # click.echo('    %s %s' % (seeds, episode[0]))
                del episodes[i]

        # remove duplicates since different sites might
        # have the same torrent
        titles = []
        for i, episode in enumerate(episodes):
            title = episode[0]
            if title in titles:
                del episodes[i]
            else:
                titles.append(title)

        # remove duplicates based on the magnet hash
        hashes = []
        for i, episode in enumerate(episodes):
            o = urllib.parse.urlparse(episode[5])
            torrent_hash = urllib.parse.parse_qs(o.query)['xt']
            torrent_hash = torrent_hash[0].split(':')[-1]
            if torrent_hash in hashes:
                del episodes[i]
            else:
                hashes.append(torrent_hash)

    def magnet_filename(self):
        se_ep = sxxexx(self.season, self.episode)
        if se_ep:
            fullname = '%s %s.magnet' % (self.show_name, se_ep)
        else:
            fullname = '%s.magnet' % (self.show_name)
        fullname = fullname.replace(' ', '_')
        return fullname

    def config_command(self, chosen_show):
        args = [i.replace('{magnet}', chosen_show) for i in Config.client]
        if args == Config.client:
            sys.exit('\nNo {magnet} replacement flag was found in config.ini, client section.')

        return args

    def download(self, chosen_show, destination, search_type='torrent'):
        """
        Pass the chosen show's data and destination to the providers
        download method and return the name of the file downloaded
        back to get-nzb.v2.py
        """

        downloaded_filename = ''
        if chosen_show.startswith("magnet:"):

            # write magnet links to a file
            if Config.magnet_dir:
                Config.magnet_dir = os.path.expanduser(Config.magnet_dir)
                fn = self.magnet_filename()
                if os.path.isdir(Config.magnet_dir):
                    full = os.path.join(Config.magnet_dir, fn)
                    with open(full, 'w') as f:
                        f.write(chosen_show)
                else:
                    sys.exit('\n"%s" does not exist' % Config.magnet_dir)

            # use a command specified in config.ini
            elif Config.client:
                args = self.config_command(chosen_show)
                try:
                    subprocess.Popen(args)
                except FileNotFoundError:
                    sys.exit('\n"%s" not found.' % args[0])

            elif platform.system() == 'Linux':
                isX = True if os.environ.get('DISPLAY') else False
                if isX:
                    app = 'xdg-open'
                else:
                    sys.exit('\nNon X usage is not supported')

                try:
                    subprocess.Popen([app, chosen_show],
                                     stderr=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL)
                except OSError:
                    sys.exit('\nYou do not have a bittorent client installed')

            elif platform.system() == 'Darwin':
                subprocess.Popen(["open", "--background", chosen_show])

            elif platform.system() == 'Windows':
                os.startfile(chosen_show)

            else:
                unknown_system = platform.platform()
                sys.exit('\nUnknown system:', unknown_system)

        else:  # is a nzb file
            final_name = ''
            # only cleans name for tv show downloads
            if self.season and self.episode:
                final_name = '%s.%s.nzb' % (
                    self.show_name.replace(' ', '.'),
                    "S%sE%s" % (self.season.rjust(2, '0'),
                                self.episode.rjust(2, '0'))
                )
            else:
                final_name = '%s.nzb' % (self.show_name)

            downloader = self.newsgroup_engines[0].Provider()
            downloaded_filename = downloader.download(
                chosen_show, destination, final_name)

        return downloaded_filename

    def progress_title(self, future):
        """Display the search engine name on the right side of the progressbar"""
        try:
            engine_name = future.result()[-1]
            # print('\n%s' % engine_name)
            engine_name += ' done'
            self.last_engine = engine_name
            return engine_name
        except AttributeError:
            engine_name = ''
            return


if __name__ == '__main__':
    test = Search('nzbindex')
    test = Search('NZBIndex')
    test = Search('x')
