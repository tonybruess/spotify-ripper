# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from colorama import Fore
from spotify_ripper.utils import *
import os
import time
import spotify
import requests
import csv
import re

import spotipy
import spotipy.client
from spotipy.oauth2 import SpotifyClientCredentials

client_credentials_sp = None

def init_client_credentials_sp():

    global client_credentials_sp
    if client_credentials_sp is None:
        client_credentials_manager = SpotifyClientCredentials()
        client_credentials_sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        client_credentials_sp.trace = False

    return client_credentials_sp

def get_album(albumURI):
    sp = init_client_credentials_sp()
    return sp.album(albumURI)

class WebAPI(object):

    def __init__(self, args, ripper):
        self.args = args
        self.ripper = ripper
        self.cache = {
            "albums_with_filter": {},
            "artists_on_album": {},
            "genres": {},
            "charts": {},
            "large_coverart": {}
        }

    def cache_result(self, name, uri, result):
        self.cache[name][uri] = result

    def get_cached_result(self, name, uri):
        return self.cache[name].get(uri)

    def request_json(self, url, msg):
        print(Fore.GREEN + "Attempting to retrieve " + msg +
              " from Spotify's Web API" + Fore.RESET)
        print(Fore.CYAN + url + Fore.RESET)
        sp = init_client_credentials_sp()
        try:
            res = sp._get(url)
        except spotify.SpotifyException as e:
            print(Fore.YELLOW + "URL returned non-200 HTTP code: " +
                  str(e.http_status) + " message: " + e.msg + Fore.RESET)
            return None
        return res

    def request_url(self, url, msg):
        print(Fore.GREEN + "Attempting to retrieve " + msg +
              " from Spotify's Web API" + Fore.RESET)
        print(Fore.CYAN + url + Fore.RESET)
        res = requests.get(url)
        if res.status_code == 200:
            return res
        else:
            print(Fore.YELLOW + "URL returned non-200 HTTP code: " +
                  str(res.status_code) + Fore.RESET)
        return None

    def api_url(self, url_path):
        return 'https://api.spotify.com/v1/' + url_path

    def charts_url(self, url_path):
        return 'https://spotifycharts.com/' + url_path

    # excludes 'appears on' albums for artist
    def get_albums_with_filter(self, uri):
        args = self.args

        album_type = ('&album_type=' + args.artist_album_type) \
            if args.artist_album_type is not None else ""

        market = ('&market=' + args.artist_album_market) \
            if args.artist_album_market is not None else ""

        def get_albums_json(offset):
            url = self.api_url(
                    'artists/' + uri_tokens[2] +
                    '/albums/?=' + album_type + market +
                    '&limit=50&offset=' + str(offset))
            return self.request_json(url, "albums")

        # check for cached result
        cached_result = self.get_cached_result("albums_with_filter", uri)
        if cached_result is not None:
            return cached_result

        # extract artist id from uri
        uri_tokens = uri.split(':')
        if len(uri_tokens) != 3:
            return []

        # it is possible we won't get all the albums on the first request
        offset = 0
        album_uris = []
        total = None
        while total is None or offset < total:
            try:
                # rate limit if not first request
                if total is None:
                    time.sleep(1.0)
                albums = get_albums_json(offset)
                if albums is None:
                    break

                # extract album URIs
                album_uris += [album['uri'] for album in albums['items']]
                offset = len(album_uris)
                if total is None:
                    total = albums['total']
            except KeyError as e:
                break
        print(str(len(album_uris)) + " albums found")
        self.cache_result("albums_with_filter", uri, album_uris)
        return album_uris

    def get_artists_on_album(self, uri):
        def get_album_json(album_id):
            url = self.api_url('albums/' + album_id)
            return self.request_json(url, "album")

        # check for cached result
        cached_result = self.get_cached_result("artists_on_album", uri)
        if cached_result is not None:
            return cached_result

        # extract album id from uri
        uri_tokens = uri.split(':')
        if len(uri_tokens) != 3:
            return None

        album = get_album_json(uri_tokens[2])
        if album is None:
            return None

        result = [artist['name'] for artist in album['artists']]
        self.cache_result("artists_on_album", uri, result)
        return result

    # genre_type can be "artist" or "album"
    def get_genres(self, genre_type, track):
        def get_genre_json(spotify_id):
            url = self.api_url(genre_type + 's/' + spotify_id)
            return self.request_json(url, "genres")

        # extract album id from uri
        item = track.artists[0] if genre_type == "artist" else track.album
        uri = item.link.uri

        # check for cached result
        cached_result = self.get_cached_result("genres", uri)
        if cached_result is not None:
            return cached_result

        uri_tokens = uri.split(':')
        if len(uri_tokens) != 3:
            return None

        json_obj = get_genre_json(uri_tokens[2])
        if json_obj is None:
            return None

        result = json_obj["genres"]
        self.cache_result("genres", uri, result)
        return result

    # doesn't seem to be officially supported by Spotify
    def get_charts(self, uri):
        def get_chart_tracks(metrics, region, time_window, from_date):
            url = self.charts_url(metrics + "/" + region + "/" + time_window +
                "/" + from_date + "/download")

            res = self.request_url(url, region + " " + metrics + " charts")
            if res is not None:
                csv_items = [enc_str(to_ascii(r)) for r in res.text.split("\n")]
                reader = csv.DictReader(csv_items)
                return ["spotify:track:" + row["URL"].split("/")[-1]
                            for row in reader]
            else:
                return []

        # check for cached result
        cached_result = self.get_cached_result("charts", uri)
        if cached_result is not None:
            return cached_result

        # spotify:charts:metric:region:time_window:date
        uri_tokens = uri.split(':')
        if len(uri_tokens) != 6:
            return None

        # some sanity checking
        valid_metrics = {"regional", "viral"}
        valid_regions = {"us", "gb", "ad", "ar", "at", "au", "be", "bg", "bo",
                         "br", "ca", "ch", "cl", "co", "cr", "cy", "cz", "de",
                         "dk", "do", "ec", "ee", "es", "fi", "fr", "gr", "gt",
                         "hk", "hn", "hu", "id", "ie", "is", "it", "lt", "lu",
                         "lv", "mt", "mx", "my", "ni", "nl", "no", "nz", "pa",
                         "pe", "ph", "pl", "pt", "py", "se", "sg", "sk", "sv",
                         "tr", "tw", "uy", "global"}
        valid_windows = {"daily", "weekly"}

        def sanity_check(val, valid_set):
            if val not in valid_set:
                print(Fore.YELLOW +
                      "Not a valid Spotify charts URI parameter: " +
                      val + Fore.RESET)
                print("Valid parameter options are: [" +
                      ", ".join(valid_set)) + "]"
                return False
            return True

        def sanity_check_date(val):
            if  re.match(r"^\d{4}-\d{2}-\d{2}$", val) is None and \
                    val != "latest":
                print(Fore.YELLOW +
                      "Not a valid Spotify charts URI parameter: " +
                      val + Fore.RESET)
                print("Valid parameter options are: ['latest', a date "
                      "(e.g. 2016-01-21)]")
                return False
            return True

        check_results = sanity_check(uri_tokens[2], valid_metrics) and \
            sanity_check(uri_tokens[3], valid_regions) and \
            sanity_check(uri_tokens[4], valid_windows) and \
            sanity_check_date(uri_tokens[5])
        if not check_results:
            print("Generally, a charts URI follow the pattern "
                  "spotify:charts:metric:region:time_window:date")
            return None

        tracks_obj = get_chart_tracks(uri_tokens[2], uri_tokens[3],
                                      uri_tokens[4], uri_tokens[5])
        charts_obj = {
            "metrics": uri_tokens[2],
            "region": uri_tokens[3],
            "time_window": uri_tokens[4],
            "from_date": uri_tokens[5],
            "tracks": tracks_obj
        }

        self.cache_result("charts", uri, charts_obj)
        return charts_obj


    def get_large_coverart(self, uri):
        def get_track_json(track_id):
            url = self.api_url('tracks/' + track_id)
            return self.request_json(url, "track")

        def get_image_data(url):
            response = self.request_url(url, "cover art")
            return response.content

        # check for cached result
        cached_result = self.get_cached_result("large_coverart", uri)
        if cached_result is not None:
            return get_image_data(cached_result)

        # extract album id from uri
        uri_tokens = uri.split(':')
        if len(uri_tokens) != 3:
            return None

        track = get_track_json(uri_tokens[2])
        if track is None:
            return None

        try:
            images = track['album']['images']
        except KeyError:
            return None

        for image in images:
            if image["width"] == 640:
                self.cache_result("large_coverart", uri, image["url"])
                return get_image_data(image["url"])

        return None

